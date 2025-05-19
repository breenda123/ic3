# quiz_api/views.py
from django.shortcuts import render
# quiz_api/views.py
from rest_framework import generics, status, views
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, JSONParser, FormParser
from .models import Module, QuestionType, Question
from .serializers import ModuleSerializer, QuestionTypeSerializer, QuestionSerializer
import openpyxl 
import logging
import json # Thêm import này

logger = logging.getLogger(__name__)

class ModuleListView(generics.ListAPIView):
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer

class QuestionTypeListView(generics.ListAPIView):
    queryset = QuestionType.objects.all()
    serializer_class = QuestionTypeSerializer

class QuestionListCreateView(generics.ListCreateAPIView):
    queryset = Question.objects.filter(is_active=True).select_related('module', 'question_type')
    serializer_class = QuestionSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser] 

    def get_queryset(self):
        queryset = super().get_queryset()
        module_id = self.request.query_params.get('module_id')
        question_type_id = self.request.query_params.get('question_type_id')
        if module_id:
            queryset = queryset.filter(module_id=module_id)
        if question_type_id:
            queryset = queryset.filter(question_type_id=question_type_id)
        return queryset

class QuestionRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser] 

    def perform_destroy(self, instance):
        if instance.question_image:
            instance.question_image.delete(save=False) 
        instance.delete()

class QuestionUploadView(views.APIView):
    parser_classes = [MultiPartParser] 

    def post(self, request, format=None):
        file_obj = request.FILES.get('file')
        
        if not file_obj:
            # This part is for when frontend sends processed JSON directly, not used with current frontend upload logic
            # but kept for potential future use.
            if isinstance(request.data, list): 
                questions_data = request.data
                questions_added_count = 0
                errors = []
                for q_data in questions_data:
                    serializer = QuestionSerializer(data=q_data)
                    if serializer.is_valid():
                        serializer.save()
                        questions_added_count += 1
                    else:
                        errors.append({'question_data': q_data, 'errors': serializer.errors})
                if errors:
                    return Response({
                        "message": f"{questions_added_count} câu hỏi được thêm. Có {len(errors)} lỗi.",
                        "errors": errors
                    }, status=status.HTTP_400_BAD_REQUEST if questions_added_count == 0 else status.HTTP_202_ACCEPTED) # CORRECTED STATUS
                return Response({"message": f"Đã thêm thành công {questions_added_count} câu hỏi từ JSON."}, status=status.HTTP_201_CREATED)
            return Response({"error": "Không có file nào được tải lên."}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"Processing uploaded file: {file_obj.name}")
        try:
            workbook = openpyxl.load_workbook(file_obj)
            sheet = workbook.active
            
            header_row_values = [cell.value for cell in sheet[1]] 
            logger.info(f"Raw headers from Excel: {header_row_values}")

            headers_from_file = [str(cell.value).strip().lower() if cell.value is not None else "" for cell in sheet[1]]
            logger.info(f"Processed headers (lowercase, stripped): {headers_from_file}")
            
            header_map = self._map_headers(headers_from_file)
            logger.info(f"Header map result: {header_map}")

            required_keys = ['module', 'question_type_code', 'question_text']
            missing_mapped_keys = [key for key in required_keys if header_map.get(key) is None] # Check if key exists and its value is not None
            
            if missing_mapped_keys:
                missing_original_headers = []
                header_definitions_for_error = self._get_header_definitions()
                for key in missing_mapped_keys:
                    missing_original_headers.append(header_definitions_for_error.get(key, [key])[0]) 

                error_msg = f"Thiếu các cột bắt buộc trong file Excel hoặc tên cột không được nhận dạng: {', '.join(missing_original_headers)}. Vui lòng kiểm tra file mẫu."
                logger.error(error_msg)
                return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)

            questions_to_create = []
            errors_parsing = []

            for i, row_cells in enumerate(sheet.iter_rows(min_row=2)): 
                row_values = [cell.value for cell in row_cells]
                if all(val is None for val in row_values): continue 

                raw_data = {}
                for key, mapped_index_val in header_map.items():
                    if key == 'option_indices': # Bỏ qua key 'option_indices' ở đây
                        continue
                    
                    if mapped_index_val is not None: 
                        if isinstance(mapped_index_val, int): 
                            if mapped_index_val < len(row_values): 
                                raw_data[key] = str(row_values[mapped_index_val]).strip() if row_values[mapped_index_val] is not None else ""
                            else:
                                raw_data[key] = "" 
                                logger.warning(f"Row {i+2}: Column index {mapped_index_val} for '{key}' is out of bounds (row has {len(row_values)} cells). Value set to empty.")
                        else: # This case should ideally not happen if _map_headers works correctly for non-list values
                            raw_data[key] = "" 
                            logger.error(f"Row {i+2}: Mapped index for '{key}' is not an integer: {mapped_index_val}. Value set to empty.")
                    else:
                        raw_data[key] = "" 
                
                raw_data['options_from_cols'] = []
                # 'option_indices' is a list of column indices
                if header_map.get('option_indices') and isinstance(header_map.get('option_indices'), list): 
                    for idx_col_option in header_map['option_indices']:
                         if isinstance(idx_col_option, int) and idx_col_option < len(row_values) and row_values[idx_col_option] is not None and str(row_values[idx_col_option]).strip() != "":
                            raw_data['options_from_cols'].append(str(row_values[idx_col_option]).strip())
                
                logger.debug(f"Raw data from Excel row {i+2}: {raw_data}")
                parsed_q_data = self._parse_excel_row(raw_data, i + 2) 
                if parsed_q_data.get("error"):
                    errors_parsing.append({"row": i + 2, "error": parsed_q_data["error"], "data": raw_data})
                    logger.warning(f"Parsing error on row {i+2}: {parsed_q_data['error']}")
                else:
                    questions_to_create.append(parsed_q_data)
            
            if not questions_to_create and errors_parsing:
                 return Response({"message": "Không có câu hỏi nào được xử lý thành công từ file.", "errors": errors_parsing}, status=status.HTTP_400_BAD_REQUEST)

            successful_saves = 0
            final_errors = list(errors_parsing) 

            for q_data in questions_to_create:
                serializer = QuestionSerializer(data=q_data)
                if serializer.is_valid():
                    try:
                        serializer.save()
                        successful_saves += 1
                    except Exception as e:
                        logger.error(f"Error saving question to DB: {q_data}, Error: {str(e)}")
                        final_errors.append({"data": q_data, "error": f"Lỗi khi lưu vào DB: {str(e)}"})
                else:
                    logger.warning(f"Serializer validation error: {q_data}, Errors: {serializer.errors}")
                    final_errors.append({"data": q_data, "error": serializer.errors})

            if successful_saves > 0 and final_errors:
                return Response({
                    "message": f"Đã thêm {successful_saves} câu hỏi. Có {len(final_errors)} lỗi.",
                    "errors": final_errors
                }, status=status.HTTP_202_ACCEPTED) # CORRECTED STATUS
            elif successful_saves > 0:
                return Response({"message": f"Đã thêm thành công {successful_saves} câu hỏi từ file Excel."}, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    "message": "Không thể thêm câu hỏi nào từ file do lỗi.",
                    "errors": final_errors
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception("Unhandled error during file upload processing:") 
            return Response({"error": f"Lỗi xử lý file không xác định: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _get_header_definitions(self):
        return {
            'module': ["module", "chủ đề"],
            'question_type_code': ["questiontype", "question type", "loại câu hỏi", "type"],
            'question_text': ["questiontext", "question text", "nội dung câu hỏi", "yêu cầu chung", "question"],
            'options_str': ["options", "option", "lựa chọn"], 
            'correct_answer_str': ["correctanswer", "correct answer", "đáp án đúng", "answer"],
            'statements_str': ["statements (t/f table, one per line)", "statements", "các câu khẳng định"],
            'correct_answers_table_str': [
                "correctanswers (t/f table, 0/1 comma-sep)", 
                "correctanswers (t/f table)", 
                "đáp án đúng cho bảng", 
                "table answers",
                "correctanswers_table" # Thêm biến thể này
            ],
            'draggable_items_str': ["draggableitems (d&d)", "draggableitems", "các mục kéo", "drag items"],
            'drop_zone_labels_str': ["dropzonelabels (d&d)", "dropzonelabels", "các mục tiêu thả", "drop zones"],
            'explanation': ["explanation", "giải thích"]
        }

    def _map_headers(self, headers_from_file):
        header_map = {}
        header_definitions = self._get_header_definitions()
        option_indices = []

        for key, possible_names in header_definitions.items():
            found = False
            for name_variant in possible_names:
                try:
                    normalized_name_variant = name_variant.strip().lower()
                    idx = headers_from_file.index(normalized_name_variant)
                    header_map[key] = idx
                    found = True
                    logger.debug(f"Mapped header for '{key}': '{normalized_name_variant}' at index {idx}")
                    break 
                except ValueError:
                    continue
            if not found:
                logger.warning(f"Header for '{key}' not found in Excel. Expected one of: {possible_names}. Will be set to None in map.")
                header_map[key] = None 

        for idx, header_name in enumerate(headers_from_file):
            # Tìm các cột có tên bắt đầu bằng "option" theo sau là số
            if header_name.startswith("option") and header_name[len("option"):].isdigit():
                option_indices.append(idx) 
                logger.debug(f"Found Option column: '{header_name}' at index {idx}")
        
        header_map['option_indices'] = sorted(option_indices) # Sắp xếp để đảm bảo thứ tự Option1, Option2...
        return header_map


    def _parse_excel_row(self, raw_data, row_number):
        question_data = {}
        try:
            module_name = raw_data.get('module')
            if not module_name: return {"error": f"Dòng {row_number}: Thiếu tên Module."}
            module_instance = Module.objects.get(module_name__iexact=module_name)
            question_data['module'] = module_instance.id
        except Module.DoesNotExist:
            return {"error": f"Dòng {row_number}: Module '{module_name}' không tồn tại trong CSDL."}
        except Exception as e:
            logger.error(f"Row {row_number}: Error finding Module '{module_name}': {str(e)}")
            return {"error": f"Dòng {row_number}: Lỗi khi tìm Module '{module_name}': {str(e)}"}


        try:
            type_code_from_file = raw_data.get('question_type_code')
            logger.info(f"Row {row_number}: Attempting to find QuestionType with code '{type_code_from_file}' (raw from Excel: '{raw_data.get('question_type_code')}')")
            if not type_code_from_file: return {"error": f"Dòng {row_number}: Thiếu mã Loại Câu Hỏi (QuestionType code)."}
            qt_instance = QuestionType.objects.get(type_code__iexact=type_code_from_file)
            question_data['question_type'] = qt_instance.id
            logger.info(f"Row {row_number}: Found QuestionType ID: {qt_instance.id} for code '{type_code_from_file}'")
        except QuestionType.DoesNotExist:
            logger.error(f"Row {row_number}: QuestionType with code '{type_code_from_file}' DOES NOT EXIST in DB.")
            all_types = list(QuestionType.objects.all().values_list('type_code', flat=True))
            logger.info(f"Available type_codes in DB: {all_types}")
            return {"error": f"Dòng {row_number}: Loại câu hỏi với mã '{type_code_from_file}' không tồn tại trong CSDL. Các mã hợp lệ: {all_types}"}
        except Exception as e:
            logger.error(f"Row {row_number}: Error finding QuestionType '{type_code_from_file}': {str(e)}")
            return {"error": f"Dòng {row_number}: Lỗi khi tìm Loại Câu Hỏi '{type_code_from_file}': {str(e)}"}


        question_data['question_text'] = raw_data.get('question_text', "")
        if not question_data['question_text']: return {"error": f"Dòng {row_number}: Thiếu nội dung câu hỏi (QuestionText)."}
        
        question_data['explanation'] = raw_data.get('explanation', "")

        type_code = qt_instance.type_code # Sử dụng type_code chuẩn từ DB

        # Sử dụng các trường *_json để truyền dữ liệu JSON dưới dạng chuỗi
        if type_code == 'multiple-choice-single' or type_code == 'multiple-choice-multiple':
            options = raw_data.get('options_from_cols', [])
            if not options and raw_data.get('options_str'): 
                 options = [opt.strip() for opt in raw_data.get('options_str').split('|') if opt.strip()]
            
            if not options or len(options) < 2 : return {"error": f"Dòng {row_number}: Trắc nghiệm cần ít nhất 2 lựa chọn."}
            question_data['options_mc_json'] = json.dumps(options) # Chuyển thành chuỗi JSON
            
            correct_answer_str = raw_data.get('correct_answer_str', "")
            if not correct_answer_str: return {"error": f"Dòng {row_number}: Thiếu đáp án đúng (CorrectAnswer)."}

            if type_code == 'multiple-choice-single':
                try:
                    ans_index = int(correct_answer_str) - 1 
                    if not (0 <= ans_index < len(options)): return {"error": f"Dòng {row_number}: Chỉ số đáp án đúng '{correct_answer_str}' không hợp lệ cho số lượng lựa chọn là {len(options)}."}
                    question_data['correct_answer_mc_single'] = ans_index # Đây là IntegerField, không cần _json
                except ValueError: return {"error": f"Dòng {row_number}: Đáp án đúng cho trắc nghiệm chọn 1 phải là một số."}
            else: # multiple-choice-multiple
                try:
                    correct_indices = [int(s.strip()) - 1 for s in correct_answer_str.split(',') if s.strip()]
                    valid_indices = [idx for idx in correct_indices if 0 <= idx < len(options)]
                    if not valid_indices: return {"error": f"Dòng {row_number}: Không có đáp án đúng hợp lệ nào cho trắc nghiệm chọn nhiều."}
                    question_data['correct_answers_mc_multiple_json'] = json.dumps(sorted(list(set(valid_indices)))) 
                except ValueError: return {"error": f"Dòng {row_number}: Đáp án đúng cho trắc nghiệm chọn nhiều phải là các số cách nhau bằng dấu phẩy."}

        elif type_code == 'true-false':
            question_data['options_mc_json'] = json.dumps(["Đúng", "Sai"]) 
            correct_answer_str = raw_data.get('correct_answer_str', "")
            if correct_answer_str not in ['0', '1']: return {"error": f"Dòng {row_number}: Đáp án cho Đúng/Sai đơn phải là 0 (Đúng) hoặc 1 (Sai)."}
            question_data['correct_answer_mc_single'] = int(correct_answer_str)

        elif type_code == 'true-false-table':
            statements = [s.strip() for s in raw_data.get('statements_str', "").split('\n') if s.strip()]
            if not statements: return {"error": f"Dòng {row_number}: Thiếu các khẳng định cho Đúng/Sai bảng."}
            question_data['statements_tf_table_json'] = json.dumps(statements)
            
            correct_answers_str = raw_data.get('correct_answers_table_str', "")
            if not correct_answers_str: return {"error": f"Dòng {row_number}: Thiếu đáp án cho Đúng/Sai bảng."}
            try:
                correct_answers = [int(s.strip()) for s in correct_answers_str.split(',') if s.strip() in ['0', '1']]
                if len(correct_answers) != len(statements): return {"error": f"Dòng {row_number}: Số lượng khẳng định ({len(statements)}) và đáp án ({len(correct_answers)}) cho Đúng/Sai bảng không khớp."}
                question_data['correct_answers_tf_table_json'] = json.dumps(correct_answers)
            except ValueError: return {"error": f"Dòng {row_number}: Đáp án cho Đúng/Sai bảng phải là các số 0 hoặc 1, cách nhau bằng dấu phẩy."}
            # question_data['options_mc_json'] = json.dumps(["Đúng", "Sai"]) # Không cần thiết cho T/F Table vì options không dùng trực tiếp

        elif type_code == 'drag-drop-match':
            draggable_items = [s.strip() for s in raw_data.get('draggable_items_str', "").split('\n') if s.strip()]
            drop_zone_labels = [s.strip() for s in raw_data.get('drop_zone_labels_str', "").split('\n') if s.strip()]
            if not draggable_items or not drop_zone_labels or len(draggable_items) != len(drop_zone_labels):
                return {"error": f"Dòng {row_number}: Số lượng mục kéo và vùng thả cho Kéo thả phải bằng nhau và không rỗng."}
            question_data['draggable_items_dd_json'] = json.dumps(draggable_items)
            question_data['drop_zone_labels_dd_json'] = json.dumps(drop_zone_labels)
        
        return question_data



def frontend_view(request):
    return render(request, 'quiz_api/index.html') # Hoặc chỉ 'index.html' nếu đặt trực tiếp trong templates/
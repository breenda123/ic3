# quiz_api/serializers.py
from rest_framework import serializers
from .models import Module, QuestionType, Question
import json # Đảm bảo đã import json

class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ['id', 'module_name']

class QuestionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionType
        fields = ['id', 'type_code', 'type_description']

class QuestionSerializer(serializers.ModelSerializer):
    module_name = serializers.CharField(source='module.module_name', read_only=True)
    question_type_code = serializers.CharField(source='question_type.type_code', read_only=True)
    
    # Các trường JSONField này sẽ được xử lý trong to_internal_value hoặc validate
    # để chấp nhận cả Python list/dict (từ JSONParser) và JSON string (từ FormParser/MultiPartParser)
    options_mc = serializers.JSONField(required=False, allow_null=True)
    correct_answers_mc_multiple = serializers.JSONField(required=False, allow_null=True)
    statements_tf_table = serializers.JSONField(required=False, allow_null=True)
    correct_answers_tf_table = serializers.JSONField(required=False, allow_null=True)
    draggable_items_dd = serializers.JSONField(required=False, allow_null=True)
    drop_zone_labels_dd = serializers.JSONField(required=False, allow_null=True)


    class Meta:
        model = Question
        fields = [
            'id', 'module', 'module_name', 'question_type', 'question_type_code', 
            'question_text', 'question_image', 'explanation',
            'options_mc', 'correct_answer_mc_single', 'correct_answers_mc_multiple',
            'statements_tf_table', 'correct_answers_tf_table',
            'draggable_items_dd', 'drop_zone_labels_dd',
            'is_active', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'module': {'write_only': True, 'allow_null': False, 'required': True},
            'question_type': {'write_only': True, 'allow_null': False, 'required': True},
            'question_image': {'required': False, 'allow_null': True} 
        }

    def _parse_json_string_field(self, data, field_name):
        """Helper to parse a field that might be a JSON string."""
        field_value = data.get(field_name)
        if isinstance(field_value, str):
            try:
                return json.loads(field_value)
            except json.JSONDecodeError:
                raise serializers.ValidationError({field_name: f"Giá trị không phải là JSON hợp lệ: '{field_value}'"})
        return field_value # Return as is if already parsed (e.g., list/dict) or None

    def validate(self, data):
        # Parse JSON string fields first if they exist (common with FormData)
        # The field names here are what the frontend sends in FormData for JSON-like data.
        # If frontend sends 'options_mc' as a stringified JSON, this will parse it.
        # If frontend sends 'options_mc_json_string', then change key here.
        # For simplicity, assume frontend sends field name matching model's JSONField name.
        
        json_field_names_from_formdata = {
            'options_mc_json': 'options_mc',
            'correct_answers_mc_multiple_json': 'correct_answers_mc_multiple',
            'statements_tf_table_json': 'statements_tf_table',
            'correct_answers_tf_table_json': 'correct_answers_tf_table',
            'draggable_items_dd_json': 'draggable_items_dd',
            'drop_zone_labels_dd_json': 'drop_zone_labels_dd',
        }

        for form_key, model_key in json_field_names_from_formdata.items():
            if form_key in data and isinstance(data[form_key], str):
                try:
                    data[model_key] = json.loads(data[form_key])
                    # del data[form_key] # Optionally remove the _json key if it's different
                except json.JSONDecodeError:
                    raise serializers.ValidationError({form_key: f"Giá trị không phải là JSON hợp lệ."})
            elif model_key in data and isinstance(data[model_key], str): # If key matches model field directly
                 try:
                    data[model_key] = json.loads(data[model_key])
                 except json.JSONDecodeError:
                    raise serializers.ValidationError({model_key: f"Giá trị không phải là JSON hợp lệ."})


        question_type_instance = data.get('question_type') 
        if not question_type_instance and self.instance:
            question_type_instance = self.instance.question_type
        
        if not question_type_instance:
             raise serializers.ValidationError({"question_type": "Loại câu hỏi là bắt buộc."})

        type_code = question_type_instance.type_code
        
        options_mc = data.get('options_mc', getattr(self.instance, 'options_mc', None) if self.instance else None)
        correct_answer_mc_single = data.get('correct_answer_mc_single', getattr(self.instance, 'correct_answer_mc_single', None) if self.instance else None)
        correct_answers_mc_multiple = data.get('correct_answers_mc_multiple', getattr(self.instance, 'correct_answers_mc_multiple', None) if self.instance else None)
        statements_tf_table = data.get('statements_tf_table', getattr(self.instance, 'statements_tf_table', None) if self.instance else None)
        correct_answers_tf_table = data.get('correct_answers_tf_table', getattr(self.instance, 'correct_answers_tf_table', None) if self.instance else None)
        draggable_items_dd = data.get('draggable_items_dd', getattr(self.instance, 'draggable_items_dd', None) if self.instance else None)
        drop_zone_labels_dd = data.get('drop_zone_labels_dd', getattr(self.instance, 'drop_zone_labels_dd', None) if self.instance else None)

        if type_code == 'multiple-choice-single':
            if not options_mc or not isinstance(options_mc, list) or len(options_mc) < 2:
                raise serializers.ValidationError({"options_mc": "Trắc nghiệm chọn 1 cần ít nhất 2 lựa chọn."})
            if correct_answer_mc_single is None or not isinstance(correct_answer_mc_single, int): # Allow 0
                raise serializers.ValidationError({"correct_answer_mc_single": "Đáp án cho trắc nghiệm chọn 1 là bắt buộc và phải là số nguyên (chỉ số)."})
            if not (0 <= correct_answer_mc_single < len(options_mc)):
                raise serializers.ValidationError({"correct_answer_mc_single": f"Chỉ số đáp án '{correct_answer_mc_single + 1}' không hợp lệ cho số lượng lựa chọn là {len(options_mc)}."})
            data['correct_answers_mc_multiple'] = None; data['statements_tf_table'] = None; data['correct_answers_tf_table'] = None; data['draggable_items_dd'] = None; data['drop_zone_labels_dd'] = None

        elif type_code == 'multiple-choice-multiple':
            if not options_mc or not isinstance(options_mc, list) or len(options_mc) < 2:
                raise serializers.ValidationError({"options_mc": "Trắc nghiệm chọn nhiều cần ít nhất 2 lựa chọn."})
            if not correct_answers_mc_multiple or not isinstance(correct_answers_mc_multiple, list) or not correct_answers_mc_multiple:
                raise serializers.ValidationError({"correct_answers_mc_multiple": "Đáp án cho trắc nghiệm chọn nhiều là bắt buộc và phải là một danh sách các chỉ số."})
            for idx in correct_answers_mc_multiple:
                if not isinstance(idx, int) or not (0 <= idx < len(options_mc)):
                    raise serializers.ValidationError({"correct_answers_mc_multiple": f"Chỉ số đáp án '{idx + 1}' không hợp lệ cho trắc nghiệm chọn nhiều."})
            data['correct_answer_mc_single'] = None; data['statements_tf_table'] = None; data['correct_answers_tf_table'] = None; data['draggable_items_dd'] = None; data['drop_zone_labels_dd'] = None

        elif type_code == 'true-false':
            data['options_mc'] = ["Đúng", "Sai"] 
            if correct_answer_mc_single is None or correct_answer_mc_single not in [0, 1]: # Allow 0
                raise serializers.ValidationError({"correct_answer_mc_single": "Với Đúng/Sai đơn, đáp án phải là 0 (Đúng) hoặc 1 (Sai)."})
            data['correct_answers_mc_multiple'] = None; data['statements_tf_table'] = None; data['correct_answers_tf_table'] = None; data['draggable_items_dd'] = None; data['drop_zone_labels_dd'] = None
            
        elif type_code == 'true-false-table':
            if not statements_tf_table or not isinstance(statements_tf_table, list) or not statements_tf_table:
                raise serializers.ValidationError({"statements_tf_table": "Cần có danh sách các khẳng định cho Đúng/Sai bảng."})
            if not correct_answers_tf_table or not isinstance(correct_answers_tf_table, list) or not correct_answers_tf_table:
                raise serializers.ValidationError({"correct_answers_tf_table": "Cần có danh sách đáp án cho Đúng/Sai bảng."})
            if len(statements_tf_table) != len(correct_answers_tf_table):
                raise serializers.ValidationError("Số lượng khẳng định và đáp án cho Đúng/Sai bảng phải bằng nhau.")
            for ans in correct_answers_tf_table:
                if ans not in [0, 1]:
                    raise serializers.ValidationError("Mỗi đáp án trong Đúng/Sai bảng phải là 0 (Đúng) hoặc 1 (Sai).")
            data['options_mc'] = None; data['correct_answer_mc_single'] = None; data['correct_answers_mc_multiple'] = None; data['draggable_items_dd'] = None; data['drop_zone_labels_dd'] = None

        elif type_code == 'drag-drop-match':
            if not draggable_items_dd or not isinstance(draggable_items_dd, list) or not draggable_items_dd:
                raise serializers.ValidationError({"draggable_items_dd": "Cần có danh sách các mục kéo cho câu hỏi Kéo thả."})
            if not drop_zone_labels_dd or not isinstance(drop_zone_labels_dd, list) or not drop_zone_labels_dd:
                raise serializers.ValidationError({"drop_zone_labels_dd": "Cần có danh sách các nhãn vùng thả cho câu hỏi Kéo thả."})
            if len(draggable_items_dd) != len(drop_zone_labels_dd):
                raise serializers.ValidationError("Số lượng mục kéo và nhãn vùng thả phải bằng nhau.")
            data['options_mc'] = None; data['correct_answer_mc_single'] = None; data['correct_answers_mc_multiple'] = None; data['statements_tf_table'] = None; data['correct_answers_tf_table'] = None
        
        return data

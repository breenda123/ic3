# quiz_api/models.py
from django.db import models

class Module(models.Model):
    module_name = models.CharField(max_length=255, unique=True, verbose_name="Tên Chủ đề")
    def __str__(self):
        return self.module_name
    class Meta:
        verbose_name = "Chủ đề"
        verbose_name_plural = "Các Chủ đề"

class QuestionType(models.Model):
    type_code = models.CharField(max_length=50, unique=True, verbose_name="Mã Loại Câu Hỏi")
    type_description = models.CharField(max_length=255, blank=True, null=True, verbose_name="Mô tả Loại Câu Hỏi")
    def __str__(self):
        return self.type_description or self.type_code
    class Meta:
        verbose_name = "Loại Câu Hỏi"
        verbose_name_plural = "Các Loại Câu Hỏi"

class Question(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, verbose_name="Chủ đề")
    question_type = models.ForeignKey(QuestionType, on_delete=models.CASCADE, verbose_name="Loại Câu Hỏi")
    question_text = models.TextField(verbose_name="Nội dung Câu Hỏi")
    
    # Hình ảnh chính cho câu hỏi
    question_image = models.ImageField(
        upload_to='question_images/', 
        blank=True, 
        null=True, 
        verbose_name="Hình ảnh cho Câu Hỏi"
    )
    
    explanation = models.TextField(blank=True, null=True, verbose_name="Giải thích")
    
    # Cấu trúc options_mc: [{"text": "Nội dung lựa chọn", "image_path": "optional_path/to/image.jpg"}, ...]
    # image_path là đường dẫn tương đối trong MEDIA_ROOT sau khi frontend tải ảnh lên.
    options_mc = models.JSONField(blank=True, null=True, verbose_name="Lựa chọn Trắc nghiệm (JSON Array)")
    
    correct_answer_mc_single = models.IntegerField(blank=True, null=True, verbose_name="Đáp án Trắc nghiệm Chọn 1 / Đúng-Sai đơn")
    correct_answers_mc_multiple = models.JSONField(blank=True, null=True, verbose_name="Đáp án Trắc nghiệm Chọn nhiều (JSON Array)")
    
    statements_tf_table = models.JSONField(blank=True, null=True, verbose_name="Khẳng định Đúng-Sai Bảng (JSON Array)")
    correct_answers_tf_table = models.JSONField(blank=True, null=True, verbose_name="Đáp án Đúng-Sai Bảng (JSON Array)")
    
    # Cân nhắc thêm image_path cho draggable_items và drop_zone_labels nếu cần
    # Ví dụ: draggable_items_dd: [{"text": "Mục A", "image_path": "path/a.jpg"}, ...]
    draggable_items_dd = models.JSONField(blank=True, null=True, verbose_name="Mục Kéo (JSON Array)")
    drop_zone_labels_dd = models.JSONField(blank=True, null=True, verbose_name="Nhãn Vùng Thả (JSON Array)")

    is_active = models.BooleanField(default=True, verbose_name="Đang hoạt động")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Ngày cập nhật")

    def __str__(self):
        return f"{self.question_text[:50]}... ({self.question_type.type_code})"

    class Meta:
        verbose_name = "Câu Hỏi"
        verbose_name_plural = "Các Câu Hỏi"
        ordering = ['-created_at']

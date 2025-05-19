from django.contrib import admin
from .models import Module, QuestionType, Question

admin.site.register(Module)
admin.site.register(QuestionType)
admin.site.register(Question)
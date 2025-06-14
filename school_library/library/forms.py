from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from PIL import Image, ImageOps
import os
from django.conf import settings
from .models import Book, BookCopy, CustomUser, Reservation, IdentificationDocument, Subject, Author

class CustomUserCreationForm(UserCreationForm):
    document_number = forms.CharField(
        max_length=50, 
        label="Номер удостоверения",
        help_text="Введите номер вашего идентификационного удостоверения для подтверждения статуса"
    )
    
    # Скрытые поля с начальными значениями
    user_type = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        initial='student'  # Начальное значение
    )
    
    grade = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=False,
        initial=None  # Начальное значение
    )
    
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'user_type', 'grade', 'document_number')
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['grade'].required = False
        # Убираем readonly-атрибуты, так как они не работают с hidden полями
        
    def clean_document_number(self):
        document_number = self.cleaned_data.get('document_number')
        
        try:
            document = IdentificationDocument.objects.get(document_number=document_number)
            if not document.is_active:
                raise ValidationError("Данное удостоверение недействительно.")
            # Сохраняем информацию о документе для использования в других методах
            self.document = document
            return document_number
        except IdentificationDocument.DoesNotExist:
            raise ValidationError("Удостоверение с таким номером не найдено.")
    
    def clean(self):
        cleaned_data = super().clean()
        # Если успешно проверен номер документа, заполняем данные из него
        if hasattr(self, 'document'):
            document = self.document
            # Обновляем данные в cleaned_data
            cleaned_data['user_type'] = document.user_type
            if document.user_type == 'student':
                cleaned_data['grade'] = document.grade
            
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        # Связываем пользователя с удостоверением
        document_number = self.cleaned_data.get('document_number')
        if document_number and hasattr(self, 'document'):
            user.identification_document = self.document
            user.user_type = self.document.user_type
            if self.document.user_type == 'student':
                user.grade = self.document.grade
                
        if commit:
            user.save()
        
        return user

class BookForm(forms.ModelForm):
    # Новые поля для создания автора и предмета
    new_author = forms.CharField(
        max_length=200, 
        required=False, 
        label="Новый автор", 
        help_text="Заполните это поле, если нужного автора нет в списке выше"
    )
    
    new_subject = forms.CharField(
        max_length=100, 
        required=False, 
        label="Новый предмет", 
        help_text="Заполните это поле, если нужного предмета нет в списке выше"
    )
    
    class Meta:
        model = Book
        fields = ['title', 'author', 'new_author', 'subject', 'new_subject', 'grade', 'book_file', 'cover', 'excerpt']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем файловые поля необязательными
        self.fields['book_file'].required = False
        self.fields['excerpt'].required = False
        
        # Если это существующая книга, делаем обложку необязательной
        if self.instance and self.instance.pk and self.instance.cover:
            self.fields['cover'].required = False
        else:
            self.fields['cover'].required = True  # Обложка обязательна только для новых книг
        
        # Обновляем виджеты для лучшего отображения
        self.fields['author'].widget.attrs['class'] = 'form-select'
        self.fields['subject'].widget.attrs['class'] = 'form-select'
        self.fields['grade'].widget = forms.Select(choices=[(i, str(i)) for i in range(1, 12)], attrs={'class': 'form-select'})
        
    def clean(self):
        cleaned_data = super().clean()
        author = cleaned_data.get('author')
        new_author = cleaned_data.get('new_author')
        subject = cleaned_data.get('subject')
        new_subject = cleaned_data.get('new_subject')
        
        # Проверяем, что указан либо существующий автор, либо новый
        if not author and not new_author:
            self.add_error('author', 'Выберите существующего автора или укажите нового')
            self.add_error('new_author', 'Выберите существующего автора или укажите нового')
        
        # Проверяем, что указан либо существующий предмет, либо новый
        if not subject and not new_subject:
            self.add_error('subject', 'Выберите существующий предмет или укажите новый')
            self.add_error('new_subject', 'Выберите существующий предмет или укажите новый')
        
        # Проверяем, что у книги есть хотя бы один файл (книга или отрывок)
        book_file = cleaned_data.get('book_file')
        excerpt = cleaned_data.get('excerpt')
        
        # Если это новая книга, то хотя бы один файл должен быть загружен
        if not self.instance.pk and not book_file and not excerpt:
            self.add_error('book_file', 'Необходимо загрузить хотя бы один файл (книгу или отрывок)')
            self.add_error('excerpt', 'Необходимо загрузить хотя бы один файл (книгу или отрывок)')
        # Если это существующая книга, то нельзя удалить оба файла
        elif self.instance.pk and not book_file and not excerpt and not self.instance.book_file and not self.instance.excerpt:
            self.add_error('book_file', 'У книги должен быть хотя бы один файл (книга или отрывок)')
            self.add_error('excerpt', 'У книги должен быть хотя бы один файл (книга или отрывок)')
        
        return cleaned_data
    
    def clean_book_file(self):
        book_file = self.cleaned_data.get('book_file')
        if book_file:
            extension = os.path.splitext(book_file.name)[1][1:].lower()
            if extension not in settings.ALLOWED_BOOK_FORMATS:
                raise forms.ValidationError(f"Недопустимый формат файла. Разрешены только: {', '.join(settings.ALLOWED_BOOK_FORMATS)}")
        return book_file
    
    def clean_cover(self):
        cover = self.cleaned_data.get('cover')
        if cover:
            extension = os.path.splitext(cover.name)[1][1:].lower()
            if extension not in settings.ALLOWED_IMAGE_FORMATS:
                raise forms.ValidationError(f"Недопустимый формат изображения. Разрешены только: {', '.join(settings.ALLOWED_IMAGE_FORMATS)}")
            
            # Проверка размера файла
            if cover.size > 5 * 1024 * 1024:  # 5 МБ
                raise forms.ValidationError("Размер файла не должен превышать 5 МБ")
                
            # Сжатие и оптимизация изображения
            try:
                img = Image.open(cover)
                
                # Если изображение слишком маленькое, выдаем предупреждение
                if img.width < 300 or img.height < 400:
                    raise forms.ValidationError("Изображение слишком маленькое. Рекомендуемый минимальный размер 300x400 пикселей.")
                
                # Преобразуем в RGB, если это не JPEG
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                    
                # Установим оптимальные размеры для обложек книг (соотношение 3:4)
                target_width, target_height = 600, 800
                
                # Если высота больше ширины (портретная ориентация), подгоняем под нужные размеры
                if img.height > img.width:
                    # Сохраняем соотношение сторон при изменении размера
                    img.thumbnail((target_width, target_height), Image.LANCZOS)
                else:
                    # Если изображение в альбомной ориентации, обрезаем его до нужных пропорций
                    img = ImageOps.fit(img, (target_width, target_height), Image.LANCZOS)
                
                # Возвращаем модифицированное изображение
                import io
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=85, optimize=True)
                output.seek(0)
                
                # Формируем новый файл для Django
                from django.core.files.uploadedfile import InMemoryUploadedFile
                return InMemoryUploadedFile(
                    output, 'ImageField',
                    f"{os.path.splitext(cover.name)[0]}.jpg",
                    'image/jpeg',
                    output.getbuffer().nbytes,
                    None
                )
            except Exception as e:
                raise forms.ValidationError(f"Ошибка обработки изображения: {str(e)}")
        return cover
        
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Обрабатываем добавление нового автора, если нужно
        new_author = self.cleaned_data.get('new_author')
        if new_author and not self.cleaned_data.get('author'):
            author, created = Author.objects.get_or_create(name=new_author)
            instance.author = author
        
        # Обрабатываем добавление нового предмета, если нужно
        new_subject = self.cleaned_data.get('new_subject')
        if new_subject and not self.cleaned_data.get('subject'):
            subject, created = Subject.objects.get_or_create(name=new_subject)
            instance.subject = subject
        
        if commit:
            instance.save()
            # Сохраняем связи many-to-many после сохранения объекта
            self.save_m2m()
            
        return instance

class BookCopyForm(forms.ModelForm):
    book = forms.ModelChoiceField(
        queryset=Book.objects.all(),
        widget=forms.HiddenInput(),
        required=False
    )
    
    class Meta:
        model = BookCopy
        fields = ['inventory_number', 'book']
        
    def clean(self):
        cleaned_data = super().clean()
        # Проверяем, что книга указана
        if not cleaned_data.get('book'):
            raise forms.ValidationError('Необходимо указать книгу для экземпляра')
        return cleaned_data

class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ['book_copy', 'due_date']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'})
        }
        
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        book_id = kwargs.pop('book_id', None)
        super().__init__(*args, **kwargs)
        
        # Показать только доступные экземпляры книг
        if 'book_copy' in self.fields:
            queryset = BookCopy.objects.filter(is_available=True)
            
            # Если указан ID книги, фильтруем только экземпляры этой книги
            if book_id:
                queryset = queryset.filter(book_id=book_id)
                
            self.fields['book_copy'].queryset = queryset
            
            # Добавляем стилизацию и изменяем отображаемый текст для экземпляров
            self.fields['book_copy'].widget.attrs.update({'class': 'form-control'})
            self.fields['book_copy'].label_from_instance = lambda obj: f"{obj.book.title} - {obj.inventory_number}"

class BookSearchForm(forms.Form):
    query = forms.CharField(label='Поиск', required=False)
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all(),
        required=False,
        label='Предмет'
    )
    grade = forms.IntegerField(
        min_value=1,
        max_value=11,
        required=False,
        label='Класс'
    )
    author = forms.ModelChoiceField(
        queryset=Author.objects.all(),
        required=False,
        label='Автор'
    ) 
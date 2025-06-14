from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator
from django.conf import settings

class IdentificationDocument(models.Model):
    """Модель для хранения данных удостоверений пользователей"""
    document_number = models.CharField(max_length=50, unique=True, verbose_name="Номер удостоверения")
    USER_TYPE_CHOICES = (
        ('student', 'Ученик'),
        ('teacher', 'Учитель'),
        ('librarian', 'Библиотекарь'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, verbose_name="Тип пользователя")
    full_name = models.CharField(max_length=255, verbose_name="ФИО")
    grade = models.IntegerField(null=True, blank=True, verbose_name="Класс (для учеников)")
    issue_date = models.DateField(verbose_name="Дата выдачи")
    expiry_date = models.DateField(verbose_name="Срок действия")
    is_active = models.BooleanField(default=True, verbose_name="Активно")
    
    def __str__(self):
        return f"{self.document_number} - {self.full_name} ({self.get_user_type_display()})"
    
    class Meta:
        verbose_name = "Удостоверение"
        verbose_name_plural = "Удостоверения"
        ordering = ['user_type', 'full_name']

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('student', 'Ученик'),
        ('teacher', 'Учитель'),
        ('librarian', 'Библиотекарь'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    grade = models.IntegerField(null=True, blank=True)
    identification_document = models.OneToOneField(
        IdentificationDocument, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Удостоверение"
    )

    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"

class Subject(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название предмета")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Предмет"
        verbose_name_plural = "Предметы"

class Author(models.Model):
    name = models.CharField(max_length=200, verbose_name="Имя автора")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Автор"
        verbose_name_plural = "Авторы"

class Book(models.Model):
    title = models.CharField(max_length=200, verbose_name="Название книги")
    author = models.ForeignKey(Author, on_delete=models.CASCADE, verbose_name="Автор")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Предмет")
    grade = models.IntegerField(verbose_name="Класс")
    
    book_file = models.FileField(
        upload_to=f'{settings.BOOKS_DIR}/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=settings.ALLOWED_BOOK_FORMATS)],
        verbose_name="Файл книги",
        null=True,
        blank=True
    )
    cover = models.ImageField(
        upload_to=f'{settings.COVERS_DIR}/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=settings.ALLOWED_IMAGE_FORMATS)],
        verbose_name="Обложка книги",
        null=True,
        blank=True
    )
    excerpt = models.FileField(
        upload_to=f'{settings.EXCERPTS_DIR}/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        verbose_name="Отрывок книги",
        null=True,
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    def __str__(self):
        return f"{self.title} ({self.author})"
    
    class Meta:
        verbose_name = "Книга"
        verbose_name_plural = "Книги"
        ordering = ['-created_at']

class BookCopy(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="copies", verbose_name="Книга")
    inventory_number = models.CharField(max_length=50, unique=True, verbose_name="Инвентарный номер")
    is_available = models.BooleanField(default=True, verbose_name="Доступна")
    
    def __str__(self):
        return f"{self.book.title} - {self.inventory_number}"
    
    class Meta:
        verbose_name = "Экземпляр книги"
        verbose_name_plural = "Экземпляры книг"

class Reservation(models.Model):
    STATUS_CHOICES = (
        ('pending', 'На рассмотрении'),
        ('approved', 'Одобрено'),
        ('rejected', 'Отклонено'),
        ('returned', 'Возвращено'),
    )
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="Пользователь")
    book_copy = models.ForeignKey(BookCopy, on_delete=models.CASCADE, verbose_name="Экземпляр книги")
    reserved_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата бронирования")
    due_date = models.DateField(verbose_name="Срок возврата")
    returned_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата возврата")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name="Статус бронирования")
    
    def __str__(self):
        return f"{self.user} - {self.book_copy.book.title}"
    
    class Meta:
        verbose_name = "Бронирование"
        verbose_name_plural = "Бронирования"
        ordering = ['-reserved_at']

class BorrowingStats(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, verbose_name="Книга")
    user_type = models.CharField(max_length=10, choices=CustomUser.USER_TYPE_CHOICES, verbose_name="Тип пользователя")
    count = models.IntegerField(default=0, verbose_name="Количество бронирований")
    month = models.IntegerField(verbose_name="Месяц")
    year = models.IntegerField(verbose_name="Год")
    
    def __str__(self):
        return f"{self.book.title} - {self.get_user_type_display()} - {self.month}/{self.year}"
    
    class Meta:
        verbose_name = "Статистика бронирования"
        verbose_name_plural = "Статистика бронирований"
        unique_together = ['book', 'user_type', 'month', 'year']

class FileDownload(models.Model):
    FILE_TYPE_CHOICES = (
        ('book', 'Книга'),
        ('excerpt', 'Отрывок'),
    )
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="Пользователь")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, verbose_name="Книга")
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, verbose_name="Тип файла")
    downloaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата скачивания")
    
    def __str__(self):
        return f"{self.user.username} - {self.book.title} ({self.get_file_type_display()}) - {self.downloaded_at.strftime('%d.%m.%Y %H:%M')}"
    
    class Meta:
        verbose_name = "Скачивание файла"
        verbose_name_plural = "Скачивания файлов"
        ordering = ['-downloaded_at']

class Overdue(models.Model):
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, verbose_name="Бронирование")
    notification_sent = models.BooleanField(default=False, verbose_name="Уведомление отправлено")
    days_overdue = models.IntegerField(default=0, verbose_name="Дней просрочено")
    
    def __str__(self):
        return f"{self.reservation.user} - {self.reservation.book_copy.book.title} - {self.days_overdue} дней просрочки"
    
    class Meta:
        verbose_name = "Просрочка"
        verbose_name_plural = "Просрочки"

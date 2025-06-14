from django.http import FileResponse, HttpResponseForbidden, Http404
from django.conf import settings
import os
from datetime import datetime, timedelta
from .models import Reservation, Overdue, BorrowingStats, FileDownload
from django.db.models import Count

def serve_protected_file(request, file_path, content_type, as_attachment=False, filename=None):
    """
    Защищенная подача файлов - только авторизованным пользователям
    
    Args:
        request: HTTP request
        file_path: путь к файлу относительно MEDIA_ROOT
        content_type: тип содержимого (MIME)
        as_attachment: отдавать как вложение (для скачивания)
        filename: имя файла для скачивания (если as_attachment=True)
    """
    if not request.user.is_authenticated:
        return HttpResponseForbidden('Доступ разрешен только авторизованным пользователям')
        
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    
    # Проверка на существование файла
    if not os.path.exists(full_path):
        raise Http404('Файл не найден')
    
    # Открываем файл в бинарном режиме
    file = open(full_path, 'rb')
        
    response = FileResponse(file, content_type=content_type)
    
    # Если нужно скачать файл
    if as_attachment:
        download_name = filename or os.path.basename(file_path)
        # Кодируем имя файла для корректного отображения в заголовке
        encoded_name = download_name.encode('utf-8').decode('latin-1')
        response['Content-Disposition'] = f'attachment; filename="{encoded_name}"'
        # Дополнительные заголовки, чтобы принудительно заставить браузер скачивать файл
        response['X-Content-Type-Options'] = 'nosniff'
        # Устанавливаем прагму no-cache
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
    else:
        # Для просмотра в браузере
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
        
    return response

def update_borrowing_stats(reservation):
    """
    Обновляет статистику бронирований
    """
    today = datetime.now()
    book = reservation.book_copy.book
    user_type = reservation.user.user_type
    
    # Проверяем, существует ли запись статистики для данной книги, типа пользователя и месяца
    stat, created = BorrowingStats.objects.get_or_create(
        book=book,
        user_type=user_type,
        month=today.month,
        year=today.year,
        defaults={'count': 0}
    )
    
    # Увеличиваем счетчик
    stat.count += 1
    stat.save()

def log_file_download(user, book, file_type):
    """
    Логирует скачивание файла и обновляет статистику скачиваний
    
    Args:
        user: пользователь, скачавший файл
        book: книга, файл которой был скачан
        file_type: тип файла (book или excerpt)
    """
    # Создаем запись о скачивании
    FileDownload.objects.create(
        user=user,
        book=book,
        file_type=file_type
    )

def get_download_stats():
    """
    Получает статистику скачиваний файлов за текущий месяц
    
    Returns:
        book_downloads: статистика скачиваний книг
        excerpt_downloads: статистика скачиваний отрывков
    """
    today = datetime.now()
    current_month_start = datetime(today.year, today.month, 1)
    
    # Получаем статистику по скачиваниям книг
    book_downloads = FileDownload.objects.filter(
        file_type='book',
        downloaded_at__gte=current_month_start
    ).values('book__title', 'book__author__name').annotate(
        total=Count('id')
    ).order_by('-total')[:10]
    
    # Получаем статистику по скачиваниям отрывков
    excerpt_downloads = FileDownload.objects.filter(
        file_type='excerpt',
        downloaded_at__gte=current_month_start
    ).values('book__title', 'book__author__name').annotate(
        total=Count('id')
    ).order_by('-total')[:10]
    
    return book_downloads, excerpt_downloads

def check_overdue_books():
    """
    Проверяет просроченные книги и обновляет соответствующие записи
    """
    today = datetime.now().date()
    
    # Получаем все активные бронирования (без даты возврата)
    active_reservations = Reservation.objects.filter(returned_at__isnull=True)
    
    for reservation in active_reservations:
        if reservation.due_date < today:
            # Книга просрочена
            days_overdue = (today - reservation.due_date).days
            
            # Создаем или обновляем запись о просрочке
            overdue, created = Overdue.objects.get_or_create(
                reservation=reservation,
                defaults={'days_overdue': days_overdue}
            )
            
            if not created:
                overdue.days_overdue = days_overdue
                overdue.save()

def get_available_book_copies():
    """
    Возвращает QuerySet доступных экземпляров книг
    """
    from .models import BookCopy
    return BookCopy.objects.filter(is_available=True) 
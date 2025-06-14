from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.http import JsonResponse, HttpResponse, FileResponse
from django.urls import reverse_lazy
from django.db.models import Q, Count
from django.utils import timezone
from datetime import datetime, timedelta
import os
import mimetypes
from django.contrib import messages

from .models import Book, BookCopy, Reservation, CustomUser, Subject, Author, BorrowingStats, Overdue, IdentificationDocument, FileDownload
from .forms import BookForm, BookCopyForm, ReservationForm, BookSearchForm, CustomUserCreationForm
from .utils import serve_protected_file, update_borrowing_stats, check_overdue_books, log_file_download, get_download_stats

# Миксины для проверки прав доступа
class LibrarianRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'librarian'

def is_librarian(user):
    return user.is_authenticated and user.user_type == 'librarian'

# Представления для книг
class BookListView(LoginRequiredMixin, ListView):
    model = Book
    template_name = 'library/book_list.html'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Book.objects.all()
        form = BookSearchForm(self.request.GET)
        
        if form.is_valid():
            query = form.cleaned_data.get('query')
            subject = form.cleaned_data.get('subject')
            grade = form.cleaned_data.get('grade')
            author = form.cleaned_data.get('author')
            
            if query:
                queryset = queryset.filter(
                    Q(title__icontains=query) | 
                    Q(author__name__icontains=query)
                )
            if subject:
                queryset = queryset.filter(subject=subject)
            if grade:
                queryset = queryset.filter(grade=grade)
            if author:
                queryset = queryset.filter(author=author)
                
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = BookSearchForm(self.request.GET)
        return context
    
    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['library/book_list_partial.html']
        return [self.template_name]

class BookDetailView(LoginRequiredMixin, DetailView):
    model = Book
    template_name = 'library/book_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        book = self.get_object()
        
        # Проверяем наличие доступных экземпляров
        available_copies = book.copies.filter(is_available=True)
        context['available_copies'] = available_copies
        context['has_available_copies'] = available_copies.exists()
        
        # Если пользователь - библиотекарь, добавляем дополнительную информацию
        if self.request.user.user_type == 'librarian':
            context['all_copies'] = book.copies.all()
            context['reservations'] = Reservation.objects.filter(
                book_copy__book=book, 
                returned_at__isnull=True
            )
        
        return context

class BookCreateView(LibrarianRequiredMixin, CreateView):
    model = Book
    form_class = BookForm
    template_name = 'library/book_form.html'
    success_url = reverse_lazy('book-list')
    
    def form_valid(self, form):
        # Обрабатываем добавление нового автора, если нужно
        new_author = form.cleaned_data.get('new_author')
        if new_author and not form.cleaned_data.get('author'):
            author, created = Author.objects.get_or_create(name=new_author)
            form.instance.author = author
        
        # Обрабатываем добавление нового предмета, если нужно
        new_subject = form.cleaned_data.get('new_subject')
        if new_subject and not form.cleaned_data.get('subject'):
            subject, created = Subject.objects.get_or_create(name=new_subject)
            form.instance.subject = subject
            
        return super().form_valid(form)

class BookUpdateView(LibrarianRequiredMixin, UpdateView):
    model = Book
    form_class = BookForm
    template_name = 'library/book_form.html'
    
    def get_success_url(self):
        return reverse_lazy('book-detail', kwargs={'pk': self.object.pk})

class BookDeleteView(LibrarianRequiredMixin, DeleteView):
    model = Book
    template_name = 'library/book_confirm_delete.html'
    success_url = reverse_lazy('book-list')

# Представления для экземпляров книг
class BookCopyCreateView(LibrarianRequiredMixin, CreateView):
    model = BookCopy
    form_class = BookCopyForm
    template_name = 'library/bookcopy_form.html'
    
    def get_initial(self):
        initial = super().get_initial()
        if 'book_id' in self.kwargs:
            initial['book'] = self.kwargs['book_id']
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'book_id' in self.kwargs:
            book_id = self.kwargs['book_id']
            context['book'] = get_object_or_404(Book, pk=book_id)
        return context
        
    def form_valid(self, form):
        if 'book_id' in self.kwargs:
            form.instance.book_id = self.kwargs['book_id']
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('book-detail', kwargs={'pk': self.object.book.pk})

class BookCopyUpdateView(LibrarianRequiredMixin, UpdateView):
    model = BookCopy
    form_class = BookCopyForm
    template_name = 'library/bookcopy_form.html'
    
    def get_success_url(self):
        return reverse_lazy('book-detail', kwargs={'pk': self.object.book.pk})

# Представления для бронирований
class ReservationCreateView(LoginRequiredMixin, CreateView):
    model = Reservation
    form_class = ReservationForm
    template_name = 'library/reservation_form.html'
    success_url = reverse_lazy('my-reservations')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        if 'pk' in self.kwargs:
            kwargs['book_id'] = self.kwargs['pk']
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'pk' in self.kwargs:
            book_id = self.kwargs['pk']
            context['book'] = get_object_or_404(Book, pk=book_id)
        return context
    
    def form_valid(self, form):
        # Привязываем бронирование к текущему пользователю
        form.instance.user = self.request.user
        form.instance.status = 'pending'
        
        response = super().form_valid(form)
        
        # Обновляем статистику
        update_borrowing_stats(self.object)
        
        # Оповещаем пользователя об ожидании подтверждения
        messages.success(self.request, 'Ваша заявка на бронирование принята и ожидает одобрения библиотекарем.')
        
        return response

class MyReservationsView(LoginRequiredMixin, ListView):
    model = Reservation
    template_name = 'library/my_reservations.html'
    
    def get_queryset(self):
        return Reservation.objects.filter(user=self.request.user).order_by('-reserved_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['today'] = timezone.now().date()
        context['status_badges'] = {
            'pending': 'bg-warning text-dark',
            'approved': 'bg-info',
            'rejected': 'bg-danger',
            'returned': 'bg-success'
        }
        return context

@login_required
@user_passes_test(is_librarian)
def return_book(request, reservation_id):
    """Отметить книгу как возвращенную"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    
    if request.method == 'POST':
        reservation.returned_at = timezone.now()
        reservation.status = 'returned'
        reservation.save()
        
        # Обновляем статус экземпляра книги
        book_copy = reservation.book_copy
        book_copy.is_available = True
        book_copy.save()
        
        # Удаляем запись о просрочке, если она существует
        Overdue.objects.filter(reservation=reservation).delete()
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        return redirect('reservation-list')
    
    return render(request, 'library/return_book_confirm.html', {'reservation': reservation})

@login_required
@user_passes_test(is_librarian)
def reservation_list(request):
    """Список всех бронирований для библиотекаря"""
    reservations = Reservation.objects.select_related('user', 'book_copy__book').all()
    today = timezone.now().date()
    
    return render(request, 'library/reservation_list.html', {
        'reservations': reservations,
        'today': today
    })

@login_required
@user_passes_test(is_librarian)
def approve_reservation(request, reservation_id):
    """Одобрение бронирования"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    
    if request.method == 'POST':
        reservation.status = 'approved'
        reservation.save()
        
        # Обновляем статус экземпляра книги, делая его недоступным
        book_copy = reservation.book_copy
        book_copy.is_available = False
        book_copy.save()
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.success(request, f'Бронирование пользователя {reservation.user.username} успешно одобрено.')
        return redirect('reservation-list')
    
    return render(request, 'library/approve_reservation_confirm.html', {'reservation': reservation})

@login_required
@user_passes_test(is_librarian)
def reject_reservation(request, reservation_id):
    """Отклонение бронирования"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    
    if request.method == 'POST':
        reservation.status = 'rejected'
        reservation.save()
        
        # Освобождаем экземпляр книги
        book_copy = reservation.book_copy
        book_copy.is_available = True
        book_copy.save()
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        return redirect('reservation-list')
    
    return render(request, 'library/reject_reservation_confirm.html', {'reservation': reservation})

@login_required
def download_excerpt(request, book_id):
    """Скачать отрывок книги"""
    book = get_object_or_404(Book, id=book_id)
    # Логируем скачивание
    log_file_download(request.user, book, 'excerpt')
    # Используем attachment вместо inline для скачивания
    return serve_protected_file(request, book.excerpt.name, 'application/pdf', as_attachment=True, 
                              filename=f"отрывок_{book.title}.pdf")

@login_required
def view_excerpt(request, book_id):
    """Просмотр отрывка книги онлайн в браузере"""
    book = get_object_or_404(Book, id=book_id)
    # Логируем просмотр
    log_file_download(request.user, book, 'excerpt')
    # Открываем для просмотра в браузере (inline)
    return serve_protected_file(request, book.excerpt.name, 'application/pdf', as_attachment=False)

@login_required
def view_book_online(request, book_id):
    """Просмотр книги онлайн"""
    book = get_object_or_404(Book, id=book_id)
    content_type = mimetypes.guess_type(book.book_file.name)[0] or 'application/octet-stream'
    return serve_protected_file(request, book.book_file.name, content_type, as_attachment=False)

@login_required
def download_book(request, book_id):
    """Скачать книгу"""
    book = get_object_or_404(Book, id=book_id)
    # Логируем скачивание
    log_file_download(request.user, book, 'book')
    content_type = mimetypes.guess_type(book.book_file.name)[0] or 'application/octet-stream'
    
    # Проверяем, является ли файл PDF, и обрабатываем его особым образом
    file_extension = book.book_file.name.split('.')[-1].lower()
    
    # Всегда скачиваем файл, а не открываем в браузере
    return serve_protected_file(request, book.book_file.name, content_type, as_attachment=True, 
                             filename=f"{book.title}.{file_extension}")

# Представления для отчетов (только для библиотекарей)
@login_required
@user_passes_test(is_librarian)
def borrowing_stats_view(request):
    """Статистика по бронированиям"""
    # Обновляем статистику просроченных книг
    check_overdue_books()
    
    # Получаем данные
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    # Статистика по типам пользователей
    user_stats = BorrowingStats.objects.filter(
        month=current_month, 
        year=current_year
    ).values('user_type').annotate(total=Count('count'))
    
    # Самые популярные книги
    popular_books = BorrowingStats.objects.filter(
        month=current_month, 
        year=current_year
    ).values('book__title', 'book__author__name').annotate(
        total=Count('count')
    ).order_by('-total')[:10]
    
    # Просроченные книги
    overdue_books = Overdue.objects.all().select_related(
        'reservation__user', 
        'reservation__book_copy__book'
    )
    
    # Получаем статистику скачиваний
    book_downloads, excerpt_downloads = get_download_stats()
    
    context = {
        'user_stats': user_stats,
        'popular_books': popular_books,
        'overdue_books': overdue_books,
        'book_downloads': book_downloads,
        'excerpt_downloads': excerpt_downloads,
    }
    
    return render(request, 'library/borrowing_stats.html', context)

@login_required
@user_passes_test(is_librarian)
def download_logs_view(request):
    """Журнал скачиваний файлов"""
    
    # Получение параметров фильтрации
    file_type = request.GET.get('file_type', '')
    user_search = request.GET.get('user', '')
    book_search = request.GET.get('book', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Базовый запрос
    downloads = FileDownload.objects.select_related('user', 'book', 'book__author').order_by('-downloaded_at')
    
    # Применение фильтров
    if file_type:
        downloads = downloads.filter(file_type=file_type)
    
    if user_search:
        downloads = downloads.filter(
            Q(user__username__icontains=user_search) | 
            Q(user__first_name__icontains=user_search) | 
            Q(user__last_name__icontains=user_search)
        )
    
    if book_search:
        downloads = downloads.filter(
            Q(book__title__icontains=book_search) | 
            Q(book__author__name__icontains=book_search)
        )
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
            downloads = downloads.filter(downloaded_at__gte=date_from_obj)
        except (ValueError, TypeError):
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            downloads = downloads.filter(downloaded_at__lte=date_to_obj)
        except (ValueError, TypeError):
            pass
    
    # Пагинация результатов
    from django.core.paginator import Paginator
    paginator = Paginator(downloads, 20)  # По 20 записей на страницу
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'file_type': file_type,
        'user_search': user_search,
        'book_search': book_search,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'library/download_logs.html', context)

# Представление для регистрации пользователей
class UserCreateView(CreateView):
    model = CustomUser
    form_class = CustomUserCreationForm
    template_name = 'registration/register.html'
    success_url = reverse_lazy('login')
    
    def form_invalid(self, form):
        """
        Переопределяем метод для вывода ошибок формы в консоль
        """
        print("Форма регистрации некорректна")
        for field, errors in form.errors.items():
            print(f"Ошибки в поле {field}: {errors}")
        
        return super().form_invalid(form)
    
    def form_valid(self, form):
        """
        Проверяем, что удостоверение существует и устанавливаем тип пользователя и класс
        """
        try:
            document_number = form.cleaned_data.get('document_number')
            document = IdentificationDocument.objects.get(document_number=document_number)
            
            # Устанавливаем правильные значения из удостоверения
            form.instance.user_type = document.user_type
            if document.user_type == 'student' and document.grade:
                form.instance.grade = document.grade
            
            # Устанавливаем связь с удостоверением
            form.instance.identification_document = document
            
            print(f"Успешная регистрация пользователя с удостоверением {document_number}")
            return super().form_valid(form)
        except IdentificationDocument.DoesNotExist:
            form.add_error('document_number', 'Удостоверение с указанным номером не найдено.')
            return self.form_invalid(form)
        except Exception as e:
            print(f"Ошибка при регистрации: {str(e)}")
            form.add_error(None, f'Произошла ошибка при регистрации: {str(e)}')
            return self.form_invalid(form)

# Главная страница
def index(request):
    # Получаем последние добавленные книги
    latest_books = Book.objects.all()[:6]
    
    # Получаем книги по предметам
    subjects = Subject.objects.all()[:5]
    books_by_subject = {}
    
    for subject in subjects:
        books_by_subject[subject] = Book.objects.filter(subject=subject)[:4]
    
    context = {
        'latest_books': latest_books,
        'subjects': subjects,
        'books_by_subject': books_by_subject,
    }
    
    return render(request, 'library/index.html', context)

@login_required
@user_passes_test(is_librarian)
def delete_book_file(request, book_id):
    """Удаление файла книги"""
    book = get_object_or_404(Book, id=book_id)
    
    if request.method == 'POST':
        # Удаляем файл
        if book.book_file:
            # Сохраняем путь к файлу
            file_path = book.book_file.path
            
            # Очищаем поле в модели
            book.book_file = None
            book.save()
            
            # Удаляем физический файл
            try:
                import os
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass  # Игнорируем ошибки при удалении
                
        return redirect('book-update', pk=book_id)
    
    return render(request, 'library/book_confirm_delete_file.html', {
        'book': book,
        'file_type': 'файл книги'
    })

@login_required
@user_passes_test(is_librarian)
def delete_book_cover(request, book_id):
    """Удаление обложки книги"""
    book = get_object_or_404(Book, id=book_id)
    
    if request.method == 'POST':
        # Удаляем файл обложки
        if book.cover:
            # Сохраняем путь к файлу
            file_path = book.cover.path
            
            # Очищаем поле в модели
            book.cover = None
            book.save()
            
            # Удаляем физический файл
            try:
                import os
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass  # Игнорируем ошибки при удалении
                
        return redirect('book-update', pk=book_id)
    
    return render(request, 'library/book_confirm_delete_file.html', {
        'book': book,
        'file_type': 'обложку'
    })

@login_required
@user_passes_test(is_librarian)
def delete_book_excerpt(request, book_id):
    """Удаление отрывка книги"""
    book = get_object_or_404(Book, id=book_id)
    
    if request.method == 'POST':
        # Удаляем файл отрывка
        if book.excerpt:
            # Сохраняем путь к файлу
            file_path = book.excerpt.path
            
            # Очищаем поле в модели
            book.excerpt = None
            book.save()
            
            # Удаляем физический файл
            try:
                import os
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass  # Игнорируем ошибки при удалении
                
        return redirect('book-update', pk=book_id)
    
    return render(request, 'library/book_confirm_delete_file.html', {
        'book': book,
        'file_type': 'отрывок'
    })

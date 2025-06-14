from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    # Основные страницы
    path('', views.index, name='index'),
    path('books/', views.BookListView.as_view(), name='book-list'),
    path('books/<int:pk>/', views.BookDetailView.as_view(), name='book-detail'),
    
    # Работа с книгами (только для библиотекарей)
    path('books/create/', views.BookCreateView.as_view(), name='book-create'),
    path('books/<int:pk>/update/', views.BookUpdateView.as_view(), name='book-update'),
    path('books/<int:pk>/delete/', views.BookDeleteView.as_view(), name='book-delete'),
    
    # Работа с экземплярами книг
    path('books/<int:book_id>/copy/create/', views.BookCopyCreateView.as_view(), name='bookcopy-create'),
    path('bookcopy/<int:pk>/update/', views.BookCopyUpdateView.as_view(), name='bookcopy-update'),
    
    # Бронирования
    path('books/<int:pk>/reserve/', views.ReservationCreateView.as_view(), name='book-reserve'),
    path('my-reservations/', views.MyReservationsView.as_view(), name='my-reservations'),
    path('return-book/<int:reservation_id>/', views.return_book, name='return-book'),
    path('reservations/', views.reservation_list, name='reservation-list'),
    path('reservations/<int:reservation_id>/approve/', views.approve_reservation, name='approve-reservation'),
    path('reservations/<int:reservation_id>/reject/', views.reject_reservation, name='reject-reservation'),
    
    # Файлы
    path('books/<int:book_id>/excerpt/', views.download_excerpt, name='download-excerpt'),
    path('books/<int:book_id>/view-excerpt/', views.view_excerpt, name='view-excerpt'),
    path('books/<int:book_id>/read/', views.view_book_online, name='read-book'),
    path('books/<int:book_id>/download/', views.download_book, name='download-book'),
    path('books/<int:book_id>/delete-file/', views.delete_book_file, name='delete-book-file'),
    path('books/<int:book_id>/delete-cover/', views.delete_book_cover, name='delete-book-cover'),
    path('books/<int:book_id>/delete-excerpt/', views.delete_book_excerpt, name='delete-book-excerpt'),
    
    # Статистика и отчеты
    path('stats/', views.borrowing_stats_view, name='borrowing-stats'),
    path('download-logs/', views.download_logs_view, name='download-logs'),
    
    # Регистрация и выход
    path('register/', views.UserCreateView.as_view(), name='register'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
]

# Для разработки, в продакшне должен обслуживаться веб-сервером
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) 
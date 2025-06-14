from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from library.models import Book, Author, Subject, BookCopy, Reservation
from django.core.files.uploadedfile import SimpleUploadedFile

CustomUser = get_user_model()

class ReservationAndAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = Author.objects.create(name="Л. Толстой")
        self.subject = Subject.objects.create(name="Литература")
        
        self.book_file = SimpleUploadedFile("war_and_peace.pdf", b"PDF content", content_type="application/pdf")
        self.excerpt_file = SimpleUploadedFile("excerpt.pdf", b"PDF content", content_type="application/pdf")

        self.book = Book.objects.create(
            title="Война и мир",
            grade=11,
            author=self.author,
            subject=self.subject,
            book_file=self.book_file,
            excerpt=self.excerpt_file
        )

        self.copy = BookCopy.objects.create(book=self.book, is_available=True)

        self.user = CustomUser.objects.create_user(
            username="student", password="12345", user_type="student"
        )
        self.client.login(username="student", password="12345")

    def test_reservation_creation(self):
        """Проверка оформления бронирования"""
        response = self.client.post(
            reverse('book-reserve', kwargs={'pk': self.book.pk}),
            data={
                'book_copy': self.copy.id,
                'due_date': (timezone.now() + timedelta(days=7)).date()
            }
        )
        self.assertEqual(response.status_code, 302)  # должен быть редирект
        reservation = Reservation.objects.first()
        self.assertIsNotNone(reservation)
        self.assertEqual(reservation.book_copy, self.copy)
        self.assertEqual(reservation.user, self.user)
        self.copy.refresh_from_db()
        

    def test_download_book(self):
        """Скачивание полной книги"""
        response = self.client.get(reverse('download-book', kwargs={'book_id': self.book.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        content = b''.join(response.streaming_content)
        self.assertIn(b"PDF content", content)

    #def test_view_book_online(self):
    #    """Просмотр книги онлайн"""
    #    response = self.client.get(reverse('read-book', kwargs={'book_id': self.book.pk}))
    #    self.assertEqual(response.status_code, 200)
    #    self.assertEqual(response['Content-Type'], 'application/pdf')
    #    content = b''.join(response.streaming_content)
    #    self.assertIn(b"PDF content", content)

    def test_view_excerpt_online(self):
        """Просмотр отрывка онлайн"""
        response = self.client.get(reverse('view-excerpt', kwargs={'book_id': self.book.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        content = b''.join(response.streaming_content)
        self.assertIn(b"PDF content", content)

    #def test_download_excerpt(self):
    #    """Скачивание отрывка"""
    #    response = self.client.get(reverse('download-excerpt', kwargs={'book_id': self.book.pk}))
    #    self.assertEqual(response.status_code, 200)
    #    self.assertEqual(response['Content-Type'], 'application/pdf')
    #    content = b''.join(response.streaming_content)
    #    self.assertIn(b"PDF content", content)

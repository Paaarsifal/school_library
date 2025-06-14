from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, Book, BookCopy, Author, Subject,
    Reservation, BorrowingStats, Overdue, IdentificationDocument, FileDownload
)

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'user_type', 'grade', 'is_staff', 'identification_document')
    list_filter = ('user_type', 'grade', 'is_staff')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Персональная информация', {'fields': ('email', 'first_name', 'last_name')}),
        ('Школьная информация', {'fields': ('user_type', 'grade', 'identification_document')}),
        ('Разрешения', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Важные даты', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'user_type', 'grade', 'identification_document', 'password1', 'password2'),
        }),
    )
    search_fields = ('username', 'email')
    raw_id_fields = ('identification_document',)

class BookCopyInline(admin.TabularInline):
    model = BookCopy
    extra = 1

class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'subject', 'grade', 'created_at')
    list_filter = ('grade', 'subject', 'author')
    search_fields = ('title', 'author__name')
    date_hierarchy = 'created_at'
    inlines = [BookCopyInline]

class BookCopyAdmin(admin.ModelAdmin):
    list_display = ('book', 'inventory_number', 'is_available')
    list_filter = ('is_available', 'book__subject', 'book__grade')
    search_fields = ('inventory_number', 'book__title')

class ReservationAdmin(admin.ModelAdmin):
    list_display = ('user', 'book_copy', 'reserved_at', 'due_date', 'returned_at', 'is_overdue')
    list_filter = ('returned_at', 'user__user_type')
    search_fields = ('user__username', 'book_copy__book__title')
    date_hierarchy = 'reserved_at'
    
    def is_overdue(self, obj):
        from django.utils import timezone
        if obj.returned_at:
            return False
        return obj.due_date < timezone.now().date()
    is_overdue.boolean = True
    is_overdue.short_description = 'Просрочено'

class BorrowingStatsAdmin(admin.ModelAdmin):
    list_display = ('book', 'user_type', 'count', 'month', 'year')
    list_filter = ('user_type', 'month', 'year')
    search_fields = ('book__title',)

class OverdueAdmin(admin.ModelAdmin):
    list_display = ('reservation', 'days_overdue', 'notification_sent')
    list_filter = ('notification_sent',)
    search_fields = ('reservation__user__username', 'reservation__book_copy__book__title')

class AuthorAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

class IdentificationDocumentAdmin(admin.ModelAdmin):
    list_display = ('document_number', 'full_name', 'user_type', 'grade', 'issue_date', 'expiry_date', 'is_active')
    list_filter = ('user_type', 'grade', 'is_active')
    search_fields = ('document_number', 'full_name')
    date_hierarchy = 'issue_date'

class FileDownloadAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'file_type', 'downloaded_at')
    list_filter = ('file_type', 'downloaded_at')
    search_fields = ('user__username', 'book__title')
    date_hierarchy = 'downloaded_at'

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Book, BookAdmin)
admin.site.register(BookCopy, BookCopyAdmin)
admin.site.register(Reservation, ReservationAdmin)
admin.site.register(BorrowingStats, BorrowingStatsAdmin)
admin.site.register(Overdue, OverdueAdmin)
admin.site.register(Author, AuthorAdmin)
admin.site.register(Subject, SubjectAdmin)
admin.site.register(IdentificationDocument, IdentificationDocumentAdmin)
admin.site.register(FileDownload, FileDownloadAdmin)

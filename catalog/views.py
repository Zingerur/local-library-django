import datetime
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy

from django.shortcuts import render, get_object_or_404
from django.views import generic
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import Book, Author, BookInstance, Genre
from .forms import RenewBookForm



def index(request):
    """Головна сторінка сайту."""
    # Загальна статистика
    num_books = Book.objects.all().count()
    num_instances = BookInstance.objects.all().count()
    num_instances_available = BookInstance.objects.filter(status__exact='a').count()
    num_authors = Author.objects.count()

    # Лічильник відвідувань (сесії)
    num_visits = request.session.get('num_visits', 0)
    request.session['num_visits'] = num_visits + 1

    context = {
        'num_books': num_books,
        'num_instances': num_instances,
        'num_instances_available': num_instances_available,
        'num_authors': num_authors,
        'num_visits': num_visits,
    }

    return render(request, 'index.html', context)


class BookListView(generic.ListView):
    """Список усіх книг."""
    model = Book
    paginate_by = 10


class BookDetailView(generic.DetailView):
    """Детальна сторінка книги."""
    model = Book


class AuthorListView(generic.ListView):
    """Список усіх авторів."""
    model = Author
    paginate_by = 10


class AuthorDetailView(generic.DetailView):
    """Детальна сторінка автора."""
    model = Author


class LoanedBooksByUserListView(LoginRequiredMixin, generic.ListView):
    """Список книг, які позичив поточний користувач."""
    model = BookInstance
    template_name = 'catalog/bookinstance_list_borrowed_user.html'
    paginate_by = 10

    def get_queryset(self):
        return (
            BookInstance.objects
            .filter(borrower=self.request.user)
            .filter(status__exact='o')
            .order_by('due_back')
        )

class LoanedBooksAllListView(PermissionRequiredMixin, generic.ListView):
    """Список ВСІХ позичених книг (тільки для бібліотекарів)."""
    model = BookInstance
    permission_required = 'catalog.can_mark_returned'
    template_name = 'catalog/bookinstance_list_borrowed_all.html'
    paginate_by = 10

    def get_queryset(self):
        return (
            BookInstance.objects
            .filter(status__exact='o')
            .order_by('due_back')
        )

class AuthorCreate(PermissionRequiredMixin, CreateView):
    model = Author
    fields = ['first_name', 'last_name', 'date_of_birth', 'date_of_death']
    initial = {'date_of_death': '11/11/2023'}
    permission_required = 'catalog.add_author'


class AuthorUpdate(PermissionRequiredMixin, UpdateView):
    model = Author
    # Можна явно вказати поля, але в туторіалі показують fields = '__all__'
    fields = '__all__'
    permission_required = 'catalog.change_author'


class AuthorDelete(PermissionRequiredMixin, DeleteView):
    model = Author
    success_url = reverse_lazy('authors')
    permission_required = 'catalog.delete_author'

class BookCreate(PermissionRequiredMixin, CreateView):
    model = Book
    fields = ['title', 'author', 'summary', 'isbn', 'genre']
    permission_required = 'catalog.add_book'

class BookUpdate(PermissionRequiredMixin, UpdateView):
    model = Book
    fields = ['title', 'author', 'summary', 'isbn', 'genre']
    permission_required = 'catalog.change_book'

class BookDelete(PermissionRequiredMixin, DeleteView):
    model = Book
    success_url = reverse_lazy('books')
    permission_required = 'catalog.delete_book'

@login_required
@permission_required('catalog.can_mark_returned', raise_exception=True)
def renew_book_librarian(request, pk):
    """Форма продовження конкретного екземпляра книги (тільки для бібліотекарів)."""
    book_instance = get_object_or_404(BookInstance, pk=pk)

    if request.method == 'POST':
        # Форма заповнена даними з запиту
        form = RenewBookForm(request.POST)

        if form.is_valid():
            # Оновлюємо дату повернення і зберігаємо
            book_instance.due_back = form.cleaned_data['renewal_date']
            book_instance.save()

            # Після успішного збереження — редірект
            return HttpResponseRedirect(reverse('all-borrowed'))

    else:
        # Початкове значення — +3 тижні від сьогодні
        proposed_renewal_date = datetime.date.today() + datetime.timedelta(weeks=3)
        form = RenewBookForm(initial={'renewal_date': proposed_renewal_date})

    context = {
        'form': form,
        'book_instance': book_instance,
    }

    return render(request, 'catalog/book_renew_librarian.html', context)


from django.test import TestCase
from django.urls import reverse

import datetime
from django.utils import timezone

from catalog.models import Author, Book, BookInstance, Genre
from django.contrib.auth.models import User, Permission


class AuthorListViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Створюємо 13 авторів для тесту пагінації
        number_of_authors = 13
        for author_num in range(number_of_authors):
            Author.objects.create(
                first_name=f'Christian {author_num}',
                last_name=f'Surname {author_num}',
            )

    def test_view_url_exists_at_desired_location(self):
        resp = self.client.get('/catalog/authors/')
        self.assertEqual(resp.status_code, 200)

    def test_view_url_accessible_by_name(self):
        resp = self.client.get(reverse('authors'))
        self.assertEqual(resp.status_code, 200)

    def test_view_uses_correct_template(self):
        resp = self.client.get(reverse('authors'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'catalog/author_list.html')

    def test_pagination_is_ten(self):
        resp = self.client.get(reverse('authors'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('is_paginated' in resp.context)
        self.assertTrue(resp.context['is_paginated'] is True)
        self.assertEqual(len(resp.context['author_list']), 10)

    def test_lists_all_authors(self):
        # Друга сторінка повинна містити 3 елементи (13 - 10)
        resp = self.client.get(reverse('authors') + '?page=2')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('is_paginated' in resp.context)
        self.assertTrue(resp.context['is_paginated'] is True)
        self.assertEqual(len(resp.context['author_list']), 3)


class LoanedBookInstancesByUserListViewTest(TestCase):
    def setUp(self):
        # Створюємо двох користувачів
        test_user1 = User.objects.create_user(username='testuser1', password='12345')
        test_user1.save()
        test_user2 = User.objects.create_user(username='testuser2', password='12345')
        test_user2.save()

        # Зберігаємо їх для використання в тестах
        self.test_user1 = test_user1
        self.test_user2 = test_user2

        # Створюємо книгу
        test_author = Author.objects.create(first_name='John', last_name='Smith')
        test_genre = Genre.objects.create(name='Fantasy')

        # language ми НЕ використовуємо, щоб не залежати від моделі Language
        test_book = Book.objects.create(
            title='Book Title',
            summary='My book summary',
            isbn='ABCDEFG',
            author=test_author,
        )

        # Прив’язуємо жанри до книги (many-to-many)
        test_book.genre.set(Genre.objects.all())
        test_book.save()

        # Створюємо 30 екземплярів BookInstance
        number_of_book_copies = 30
        for book_copy in range(number_of_book_copies):
            return_date = timezone.now() + datetime.timedelta(days=book_copy % 5)
            if book_copy % 2:
                the_borrower = test_user1
            else:
                the_borrower = test_user2

            status = 'm'  # спочатку всі "доступні" (not on loan)
            BookInstance.objects.create(
                book=test_book,
                imprint='Unlikely Imprint, 2016',
                due_back=return_date,
                borrower=the_borrower,
                status=status,
            )

    def test_redirect_if_not_logged_in(self):
        resp = self.client.get(reverse('my-borrowed'))
        self.assertRedirects(resp, '/accounts/login/?next=/catalog/mybooks/')

    def test_logged_in_uses_correct_template(self):
        login = self.client.login(username='testuser1', password='12345')
        self.assertTrue(login)

        resp = self.client.get(reverse('my-borrowed'))
        # користувач залогінився
        self.assertEqual(str(resp.context['user']), 'testuser1')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'catalog/bookinstance_list_borrowed_user.html')

    def test_only_borrowed_books_in_list(self):
        login = self.client.login(username='testuser1', password='12345')
        self.assertTrue(login)

        resp = self.client.get(reverse('my-borrowed'))
        self.assertEqual(str(resp.context['user']), 'testuser1')
        self.assertEqual(resp.status_code, 200)

        # спочатку в списку не повинно бути жодної книги
        self.assertTrue('bookinstance_list' in resp.context)
        self.assertEqual(len(resp.context['bookinstance_list']), 0)

        # робимо 10 книг "on loan" (status='o')
        get_ten_books = BookInstance.objects.all()[:10]
        for copy in get_ten_books:
            copy.status = 'o'
            copy.save()

        resp = self.client.get(reverse('my-borrowed'))
        self.assertEqual(str(resp.context['user']), 'testuser1')
        self.assertEqual(resp.status_code, 200)

        self.assertTrue('bookinstance_list' in resp.context)
        # Перевіряємо, що всі книги в списку належать testuser1 і статус 'o'
        for bookitem in resp.context['bookinstance_list']:
            self.assertEqual(resp.context['user'], bookitem.borrower)
            self.assertEqual('o', bookitem.status)

    def test_pages_ordered_by_due_date(self):
        # робимо всі книги "on loan"
        for copy in BookInstance.objects.all():
            copy.status = 'o'
            copy.save()

        login = self.client.login(username='testuser1', password='12345')
        self.assertTrue(login)

        resp = self.client.get(reverse('my-borrowed'))
        self.assertEqual(str(resp.context['user']), 'testuser1')
        self.assertEqual(resp.status_code, 200)

        # на сторінці повинно бути 10 екземплярів
        self.assertEqual(len(resp.context['bookinstance_list']), 10)
        last_date = None
        for copy in resp.context['bookinstance_list']:
            if last_date is None:
                last_date = copy.due_back
            else:
                self.assertTrue(last_date <= copy.due_back)
                last_date = copy.due_back


class RenewBookInstancesViewTest(TestCase):
    def setUp(self):
        # Створюємо користувачів
        test_user1 = User.objects.create_user(username='testuser1', password='12345')
        test_user1.save()

        test_user2 = User.objects.create_user(username='testuser2', password='12345')
        test_user2.save()

        # Додаємо test_user2 право 'can_mark_returned'
        permission = Permission.objects.get(name='Set book as returned')
        test_user2.user_permissions.add(permission)
        test_user2.save()

        self.test_user1 = test_user1
        self.test_user2 = test_user2

        # Створюємо книгу
        test_author = Author.objects.create(first_name='John', last_name='Smith')
        test_genre = Genre.objects.create(name='Fantasy')

        test_book = Book.objects.create(
            title='Book Title',
            summary='My book summary',
            isbn='ABCDEFG',
            author=test_author,
        )

        test_book.genre.set(Genre.objects.all())
        test_book.save()

        # Створюємо два BookInstance
        return_date = datetime.date.today() + datetime.timedelta(days=5)
        self.test_bookinstance1 = BookInstance.objects.create(
            book=test_book,
            imprint='Unlikely Imprint, 2016',
            due_back=return_date,
            borrower=test_user1,
            status='o',
        )
        self.test_bookinstance2 = BookInstance.objects.create(
            book=test_book,
            imprint='Unlikely Imprint, 2016',
            due_back=return_date,
            borrower=test_user2,
            status='o',
        )

    def test_redirect_if_not_logged_in(self):
        resp = self.client.get(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk})
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith('/accounts/login/'))

    def test_redirect_if_logged_in_but_not_correct_permission(self):
        login = self.client.login(username='testuser1', password='12345')
        self.assertTrue(login)

        resp = self.client.get(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk})
        )
        # Користувач залогінений, але без permission → 403 (бо raise_exception=True)
        self.assertEqual(resp.status_code, 403)

    def test_logged_in_with_permission_borrowed_book(self):
        login = self.client.login(username='testuser2', password='12345')
        self.assertTrue(login)

        resp = self.client.get(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance2.pk})
        )
        self.assertEqual(resp.status_code, 200)

    def test_logged_in_with_permission_another_users_borrowed_book(self):
        login = self.client.login(username='testuser2', password='12345')
        self.assertTrue(login)

        resp = self.client.get(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk})
        )
        self.assertEqual(resp.status_code, 200)

    def test_HTTP404_for_invalid_book_if_logged_in(self):
        import uuid

        test_uid = uuid.uuid4()
        login = self.client.login(username='testuser2', password='12345')
        self.assertTrue(login)

        resp = self.client.get(
            reverse('renew-book-librarian', kwargs={'pk': test_uid})
        )
        self.assertEqual(resp.status_code, 404)

    def test_uses_correct_template(self):
        login = self.client.login(username='testuser2', password='12345')
        self.assertTrue(login)

        resp = self.client.get(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'catalog/book_renew_librarian.html')

    def test_form_renewal_date_initially_has_date_three_weeks_in_future(self):
        login = self.client.login(username='testuser2', password='12345')
        self.assertTrue(login)

        resp = self.client.get(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk})
        )
        self.assertEqual(resp.status_code, 200)

        date_3_weeks_in_future = datetime.date.today() + datetime.timedelta(weeks=3)
        self.assertEqual(
            resp.context['form'].initial['renewal_date'],
            date_3_weeks_in_future,
        )

    def test_redirects_to_all_borrowed_book_list_on_success(self):
        login = self.client.login(username='testuser2', password='12345')
        self.assertTrue(login)

        valid_date_in_future = datetime.date.today() + datetime.timedelta(weeks=2)
        resp = self.client.post(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}),
            {'renewal_date': valid_date_in_future},
        )
        self.assertRedirects(resp, reverse('all-borrowed'))

    def test_form_invalid_renewal_date_past(self):
        login = self.client.login(username='testuser2', password='12345')
        self.assertTrue(login)

        date_in_past = datetime.date.today() - datetime.timedelta(weeks=1)
        resp = self.client.post(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}),
            {'renewal_date': date_in_past},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(
            resp.context['form'],
            'renewal_date',
            'Invalid date - renewal in past',
        )

    def test_form_invalid_renewal_date_future(self):
        login = self.client.login(username='testuser2', password='12345')
        self.assertTrue(login)

        invalid_date_in_future = datetime.date.today() + datetime.timedelta(weeks=5)
        resp = self.client.post(
            reverse('renew-book-librarian', kwargs={'pk': self.test_bookinstance1.pk}),
            {'renewal_date': invalid_date_in_future},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFormError(
            resp.context['form'],
            'renewal_date',
            'Invalid date - renewal more than 4 weeks ahead',
        )

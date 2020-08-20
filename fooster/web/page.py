import html
import os.path

from fooster import web


__all__ = ['PageHandler', 'PageErrorHandler', 'new_error']


class PageHandler(web.HTTPHandler):
    directory = '.'
    page = 'index.html'

    def format(self, page):
        return page

    def do_get(self):
        self.response.headers.set('Content-Type', 'text/html; charset=' + web.default_encoding)

        with open(os.path.join(self.directory, self.page), 'r') as file:
            page = file.read()

        return 200, self.format(page)


class PageErrorHandler(web.HTTPErrorHandler):
    directory = '.'
    page = 'error.html'

    def format(self, page):
        if self.error.status_message:
            status_message = html.escape(self.error.status_message)
        else:
            status_message = html.escape(web.status_messages[self.error.code])

        if self.error.message:
            message = html.escape(self.error.message)
        else:
            message = str(self.error.code) + ' - ' + status_message

        return page.format(code=self.error.code, status_message=status_message, message=message)

    def respond(self):
        self.response.headers.set('Content-Type', 'text/html; charset=' + web.default_encoding)

        with open(os.path.join(self.directory, self.page), 'r') as file:
            page = file.read()

        if self.error.status_message:
            return self.error.code, self.error.status_message, self.format(page)
        else:
            return self.error.code, self.format(page)


def new_error(error='[0-9]{3}', *, handler=PageErrorHandler):
    return {error: handler}

import io
import threading
import time

from web import web

import fake


test_message = b'More test time!'
test_string = test_message.decode('utf-8')


def run(handler, handler_args={}, socket=None, server=None):
    if not socket:
        socket = fake.FakeSocket()

    if not server:
        server = fake.FakeHTTPServer()

    request_obj = fake.FakeHTTPRequest(socket, ('127.0.0.1', 1337), server, handler=handler, handler_args=handler_args, response=web.HTTPResponse)
    response_obj = request_obj.response

    response_obj.handle()

    value = response_obj.wfile.getvalue()

    response_obj.close()

    # response line comes before firt '\r\n'
    response_line = value.split('\r\n'.encode(web.http_encoding), 1)[0]

    # body should happen after '\r\n\r\n' at the end of the HTTP stuff
    body = value.split('\r\n\r\n'.encode(web.http_encoding), 1)[1]

    return response_obj, response_line, response_obj.headers, body


def test_atomic_wait():
    class MyHandler(web.HTTPHandler):
        nonatomic = True
        handled = False

        def respond(self):
            MyHandler.handled = True
            return 200, test_message

    class OtherHandler(web.HTTPHandler):
        nonatomic = True
        handled = False

        def respond(self):
            OtherHandler.handled = True
            return 200, test_message

    class SpecialHandler(web.HTTPHandler):
        nonatomic = False

        stop = threading.Event()
        waiting = threading.Event()

        def respond(self):
            SpecialHandler.waiting.set()
            SpecialHandler.stop.wait()

            return 204, ''

    # both must have the same server
    server = fake.FakeHTTPServer()

    # both handlers should have the same fake resource '/' and should therefore block since the first one is atomic
    special = threading.Thread(target=run, args=(SpecialHandler,), kwargs={'server': server})
    my = threading.Thread(target=run, args=(MyHandler,), kwargs={'server': server})
    other = threading.Thread(target=run, args=(OtherHandler,), kwargs={'server': server})

    try:
        special.start()

        # wait until the handler is blocking
        SpecialHandler.waiting.wait(timeout=1)

        # make sure it is locked once
        assert '/' in server.res_lock.locks
        assert server.res_lock.locks['/'][0].threads == 1

        my.start()

        # wait a bit
        time.sleep(0.1)

        # make sure that the my thread did not handle the request
        assert not MyHandler.handled
        assert not my.is_alive()
        assert server.res_lock.locks['/'][0].threads == 1

        # make sure special has been here the whole time
        assert special.is_alive()

        # stop special handler
        SpecialHandler.stop.set()

        # wait a bit
        time.sleep(0.1)

        # make sure all threads exited
        assert not special.is_alive()

        # try my and other threads now
        other.start()

        # wait a bit
        time.sleep(0.1)

        # make sure both were handled
        assert OtherHandler.handled
        assert not other.is_alive()

        # make sure we removed the lock
        assert '/' not in server.res_lock.locks
    finally:
        # join everything
        SpecialHandler.stop.set()
        special.join(timeout=1)
        my.join(timeout=1)
        other.join(timeout=1)


def test_http_error():
    response, response_line, headers, body = run(web.DummyHandler, {'error': web.HTTPError(402)})

    assert response_line == 'HTTP/1.1 402 Payment Required'.encode(web.http_encoding)


def test_general_error():
    response, response_line, headers, body = run(web.DummyHandler, {'error': TypeError()})

    assert response_line == 'HTTP/1.1 500 Internal Server Error'.encode(web.http_encoding)


def test_error_headers():
    error_headers = web.HTTPHeaders()
    error_headers.set('Test', 'True')

    response, response_line, headers, body = run(web.DummyHandler, {'error': web.HTTPError(402, headers=error_headers)})

    assert response_line == 'HTTP/1.1 402 Payment Required'.encode(web.http_encoding)

    assert headers.get('Test') == 'True'


def test_headers_clear():
    class MyHandler(web.HTTPHandler):
        def respond(self):
            self.response.headers.set('Test', 'True')

            raise web.HTTPError(402)

    response, response_line, headers, body = run(MyHandler)

    assert headers.get('Test') is None


def test_error_handler():
    class ErrorHandler(web.HTTPErrorHandler):
        def respond(self):
            self.response.headers.set('Test', 'True')

            return 402, b''

    server = fake.FakeHTTPServer(error_routes={'500': ErrorHandler})

    response, response_line, headers, body = run(web.DummyHandler, {'error': TypeError()}, server=server)

    assert response_line == 'HTTP/1.1 402 Payment Required'.encode(web.http_encoding)

    assert headers.get('Test') == 'True'

    assert body == b''


def test_error_handler_error():
    class ErrorHandler(web.HTTPErrorHandler):
        def respond(self):
            self.response.headers.set('Test', 'True')

            raise TypeError()

    server = fake.FakeHTTPServer(error_routes={'500': ErrorHandler})

    response, response_line, headers, body = run(web.DummyHandler, {'error': TypeError()}, server=server)

    assert response_line == 'HTTP/1.1 500 Internal Server Error'.encode(web.http_encoding)

    assert headers.get('Test') is None
    assert headers.get('Content-Length') == '28'
    assert headers.get('Server') == web.server_version
    assert headers.get('Date')

    assert body == b'500 - Internal Server Error\n'


def test_response_io():
    class MyHandler(web.HTTPHandler):
        def respond(self):
            return 200, io.BytesIO(test_message)

    response, response_line, headers, body = run(MyHandler)

    assert headers.get('Transfer-Encoding') == 'chunked'
    assert headers.get('Content-Length') is None

    assert body == ('{:x}'.format(len(test_message)) + '\r\n').encode(web.http_encoding) + test_message + '\r\n'.encode(web.http_encoding) + '0\r\n\r\n'.encode(web.http_encoding)


def test_response_io_length():
    class MyHandler(web.HTTPHandler):
        def respond(self):
            self.response.headers.set('Content-Length', '2')

            return 200, io.BytesIO(test_message)

    response, response_line, headers, body = run(MyHandler)

    assert headers.get('Content-Length') == '2'

    assert body == test_message[0:2]


def test_response_str():
    class MyHandler(web.HTTPHandler):
        def respond(self):
            return 200, test_message.decode('utf-8')

    response, response_line, headers, body = run(MyHandler)

    assert headers.get('Content-Length') == str(len(test_message))

    assert body == test_message


def test_response_bytes():
    class MyHandler(web.HTTPHandler):
        def respond(self):
            return 200, test_message

    response, response_line, headers, body = run(MyHandler)

    assert headers.get('Content-Length') == str(len(test_message))

    assert body == test_message


def test_response_length():
    class MyHandler(web.HTTPHandler):
        def respond(self):
            self.response.headers.set('Content-Length', '2')

            return 200, test_message

    response, response_line, headers, body = run(MyHandler)

    assert headers.get('Content-Length') == str(len(test_message))

    assert body == test_message


def test_connection_close():
    class MyHandler(web.HTTPHandler):
        def respond(self):
            return 204, ''

    response, response_line, headers, body = run(MyHandler)

    assert headers.get('Connection') is None

    class CloseHandler(web.HTTPHandler):
        def respond(self):
            self.request.keepalive = False

            return 204, ''

    response, response_line, headers, body = run(CloseHandler)

    assert headers.get('Connection') == 'close'


def test_no_write_io():
    class MyHandler(web.HTTPHandler):
        def respond(self):
            self.response.write_body = False

            return 200, test_message

    response, response_line, headers, body = run(MyHandler)

    assert response_line == 'HTTP/1.1 200 OK'.encode(web.http_encoding)

    assert body == b''


def test_no_write_bytes():
    class MyHandler(web.HTTPHandler):
        def respond(self):
            self.response.write_body = False

            return 200, io.BytesIO(test_message)

    response, response_line, headers, body = run(MyHandler)

    assert response_line == 'HTTP/1.1 200 OK'.encode(web.http_encoding)

    assert body == b''


def test_write_error():
    class EvilHandler(web.HTTPHandler):
        def respond(self):
            self.response.headers.set('Content-Length', 'bad')

            return 200, io.BytesIO(test_message)

    response, response_line, headers, body = run(EvilHandler)

    assert response_line == 'HTTP/1.1 200 OK'.encode(web.http_encoding)

    assert headers.get('Content-Length') == 'bad'

    assert body == b''


def test_log_request():
    class MyHandler(web.HTTPHandler):
        def respond(self):
            return 200, test_message

    server = fake.FakeHTTPServer()

    response, response_line, headers, body = run(MyHandler, server=server)

    assert response_line == 'HTTP/1.1 200 OK'.encode(web.http_encoding)

    assert body == test_message

    assert server.log.access_log.getvalue() == '127.0.0.1 - - [01/Jan/1970:00:00:00 -0000] "GET / HTTP/1.1" 200 15\n'
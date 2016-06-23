import json

from web import web, json as wjson

import fake


test_object = {'1': 1, '2': 2, '3': 3}
test_string = json.dumps(test_object).encode()


def test_json_encode():
    class TestHandler(wjson.JSONHandler):
        def do_get(self):
            return 200, test_object

    request = fake.FakeHTTPRequest(None, ('', 0), None, method='GET', handler=TestHandler)

    headers, response = request.response.headers, request.handler.respond()

    assert headers.get('Content-Type') == 'application/json'

    assert response[0] == 200
    assert response[1] == test_string


def test_json_decode():
    class TestHandler(wjson.JSONHandler):
        def do_post(self):
            return 200, {'type': str(type(self.request.body))}

    json_headers = web.HTTPHeaders()
    json_headers.set('Content-Type', 'application/json')

    request = fake.FakeHTTPRequest(None, ('', 0), None, headers=json_headers, body=test_string, method='POST', handler=TestHandler)

    headers, response = request.response.headers, request.handler.respond()

    assert headers.get('Content-Type') == 'application/json'

    assert response[0] == 200
    assert response[1] == json.dumps({'type': str(type(test_object))}).encode(web.default_encoding)


def test_json_nodecode():
    class TestHandler(wjson.JSONHandler):
        def do_post(self):
            return 200, {'type': str(type(self.request.body))}

    request = fake.FakeHTTPRequest(None, ('', 0), None, body=test_string, method='POST', handler=TestHandler)

    headers, response = request.response.headers, request.handler.respond()

    assert headers.get('Content-Type') == 'application/json'

    assert response[0] == 200
    assert response[1] == json.dumps({'type': str(bytes)}).encode(web.default_encoding)
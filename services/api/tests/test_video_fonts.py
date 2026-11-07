from test_api import app as app
from test_api import client as client
from test_api import login


def test_preview_fonts_require_owner_and_never_accept_arbitrary_paths(client):
    assert client.get("/video-studio/fonts/sans").status_code == 401
    login(client)
    response = client.get("/video-studio/fonts/sans")
    if response.status_code == 200:
        assert response.headers["content-type"] == "font/ttf"
        assert response.headers["cache-control"] == "private, no-store"
        assert len(response.content) > 100
    else:
        assert response.status_code == 404
    assert client.get("/video-studio/fonts/unknown").status_code == 422
    assert client.get("/video-studio/fonts/../../secret").status_code == 404

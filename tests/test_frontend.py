from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import obtener_sesion
from app.main import app


def test_frontend_y_recursos_estaticos() -> None:
    with TestClient(app) as cliente:
        pagina = cliente.get("/")
        estilos = cliente.get("/static/styles.css")
        javascript = cliente.get("/static/app.js")

    assert pagina.status_code == 200
    assert "HuellaVet" in pagina.text
    assert "Panel general" in pagina.text
    assert estilos.status_code == 200
    assert "--sage-700" in estilos.text
    assert javascript.status_code == 200
    assert "renderDashboard" in javascript.text


def test_listados_necesarios_para_el_frontend(sesion: Session) -> None:
    def reemplazar_sesion():
        yield sesion

    app.dependency_overrides[obtener_sesion] = reemplazar_sesion
    try:
        with TestClient(app) as cliente:
            aplicaciones = cliente.get("/api/vacunas/aplicaciones")
            muestras = cliente.get("/api/muestras")
            envios = cliente.get("/api/envios")
    finally:
        app.dependency_overrides.clear()

    assert aplicaciones.status_code == 200
    assert aplicaciones.json() == []
    assert muestras.status_code == 200
    assert muestras.json() == []
    assert envios.status_code == 200
    assert envios.json() == []

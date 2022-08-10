"""
Cit Servicios, vistas
"""
import json
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from lib.datatables import get_datatable_parameters, output_datatable_json
from lib.safe_string import safe_clave, safe_string, safe_message

from citas_admin.blueprints.bitacoras.models import Bitacora
from citas_admin.blueprints.cit_categorias.models import CitCategoria
from citas_admin.blueprints.cit_servicios.models import CitServicio
from citas_admin.blueprints.cit_servicios.forms import CitServicioForm
from citas_admin.blueprints.modulos.models import Modulo
from citas_admin.blueprints.permisos.models import Permiso
from citas_admin.blueprints.usuarios.decorators import permission_required

from citas_admin.blueprints.oficinas.models import Oficina

MODULO = "CIT SERVICIOS"

cit_servicios = Blueprint("cit_servicios", __name__, template_folder="templates")


@cit_servicios.before_request
@login_required
@permission_required(MODULO, Permiso.VER)
def before_request():
    """Permiso por defecto"""


@cit_servicios.route("/cit_servicios/datatable_json", methods=["GET", "POST"])
def datatable_json():
    """DataTable JSON para listado de Servicios"""
    # Tomar parámetros de Datatables
    draw, start, rows_per_page = get_datatable_parameters()
    # Consultar
    consulta = CitServicio.query
    if "estatus" in request.form:
        consulta = consulta.filter_by(estatus=request.form["estatus"])
    else:
        consulta = consulta.filter_by(estatus="A")
    if "cit_categoria_id" in request.form:
        consulta = consulta.filter_by(cit_categoria_id=request.form["cit_categoria_id"])
    registros = consulta.order_by(CitServicio.clave).offset(start).limit(rows_per_page).all()
    total = consulta.count()
    # Elaborar datos para DataTable
    data = []
    for resultado in registros:
        data.append(
            {
                "detalle": {
                    "clave": resultado.clave,
                    "url": url_for("cit_servicios.detail", cit_servicio_id=resultado.id),
                },
                "descripcion": resultado.descripcion,
                "duracion": resultado.duracion.strftime("%H:%M"),
                "documentos_limite": resultado.documentos_limite,
                "cit_categoria": {
                    "nombre": resultado.cit_categoria.nombre,
                    "url": url_for("cit_categorias.detail", cit_categoria_id=resultado.cit_categoria.id),
                },
                "desde": "-" if resultado.desde is None else resultado.desde.strftime("%H:%M"),
                "hasta": "-" if resultado.hasta is None else resultado.hasta.strftime("%H:%M"),
                "dias_habiles": "-" if resultado.dias_habiles == "" else _conversion_dias_habiles_numero_letra(resultado.dias_habiles),
            }
        )
    # Entregar JSON
    return output_datatable_json(draw, total, data)


@cit_servicios.route("/cit_servicios")
def list_active():
    """Listado de Servicios activos"""
    return render_template(
        "cit_servicios/list.jinja2",
        filtros=json.dumps({"estatus": "A"}),
        titulo="Servicios",
        estatus="A",
    )


@cit_servicios.route("/cit_servicios/inactivos")
@permission_required(MODULO, Permiso.MODIFICAR)
def list_inactive():
    """Listado de Servicios inactivos"""
    return render_template(
        "cit_servicios/list.jinja2",
        filtros=json.dumps({"estatus": "B"}),
        titulo="Servicios inactivos",
        estatus="B",
    )


@cit_servicios.route("/cit_servicios/<int:cit_servicio_id>")
def detail(cit_servicio_id):
    """Detalle de un Servicio"""
    cit_servicio = CitServicio.query.get_or_404(cit_servicio_id)

    horario = ""
    if cit_servicio.desde is None:
        horario = "No se especifica horario, se utilizará el de su oficina."
    else:
        horario = f"{cit_servicio.desde} hasta {cit_servicio.hasta}"

    dias_habiles = _conversion_dias_habiles_numero_letra(cit_servicio.dias_habiles)
    if dias_habiles == "LUNES, MARTES, MIERCOLES, JUEVES, VIERNES,":
        dias_habiles = "LUNES A VIERNES"

    return render_template(
        "cit_servicios/detail.jinja2",
        cit_servicio=cit_servicio,
        horario=horario,
        dias_habiles=dias_habiles,
    )


@cit_servicios.route("/cit_servicios/nuevo/<int:cit_categoria_id>", methods=["GET", "POST"])
@permission_required(MODULO, Permiso.CREAR)
def new(cit_categoria_id):
    """Nuevo Servicio"""
    cit_categoria = CitCategoria.query.get_or_404(cit_categoria_id)
    form = CitServicioForm()
    if form.validate_on_submit():
        # Validar que la clave no se repita
        clave = safe_clave(form.clave.data)
        if CitServicio.query.filter_by(clave=clave).first():
            flash("La clave ya está en uso. Debe de ser única.", "warning")
        else:
            if form.documentos_limite.data:
                documentos_limite = int(form.documentos_limite.data)
            else:
                documentos_limite = 0
            cit_servicio = CitServicio(
                cit_categoria=cit_categoria,
                clave=clave,
                descripcion=safe_string(form.descripcion.data, max_len=64),
                duracion=form.duracion.data,
                documentos_limite=documentos_limite,
            )
            cit_servicio.save()
            bitacora = Bitacora(
                modulo=Modulo.query.filter_by(nombre=MODULO).first(),
                usuario=current_user,
                descripcion=safe_message(f"Nuevo Servicio {cit_servicio.descripcion}"),
                url=url_for("cit_servicios.detail", cit_servicio_id=cit_servicio.id),
            )
            bitacora.save()
            flash(bitacora.descripcion, "success")
            return redirect(bitacora.url)
    form.cit_categoria_nombre.data = cit_categoria.nombre
    return render_template(
        "cit_servicios/new.jinja2",
        form=form,
        cit_categoria=cit_categoria,
    )


@cit_servicios.route("/cit_servicios/edicion/<int:cit_servicio_id>", methods=["GET", "POST"])
@permission_required(MODULO, Permiso.MODIFICAR)
def edit(cit_servicio_id):
    """Editar Servicio"""
    cit_servicio = CitServicio.query.get_or_404(cit_servicio_id)
    form = CitServicioForm()
    if form.validate_on_submit():
        es_valido = True
        # Si cambia la clave verificar que no este en uso
        clave = safe_clave(form.clave.data)
        if cit_servicio.clave != clave:
            cit_servicio_existente = CitServicio.query.filter_by(clave=clave).first()
            if cit_servicio_existente and cit_servicio_existente.id != cit_servicio.id:
                es_valido = False
                flash("La clave ya está en uso. Debe de ser única.", "warning")
        # Si es valido actualizar
        if es_valido:
            cit_servicio.clave = clave
            cit_servicio.descripcion = safe_string(form.descripcion.data, max_len=64)
            cit_servicio.duracion = form.duracion.data
            if form.documentos_limite.data:
                cit_servicio.documentos_limite = int(form.documentos_limite.data)
            else:
                cit_servicio.documentos_limite = 0
            cit_servicio.desde = form.desde.data
            cit_servicio.hasta = form.hasta.data
            dias_habiles = _conversion_dias_habiles_letra_numero(form.dias_habiles.data)
            if dias_habiles == "01234":
                dias_habiles = ""
            cit_servicio.dias_habiles = dias_habiles
            cit_servicio.save()
            bitacora = Bitacora(
                modulo=Modulo.query.filter_by(nombre=MODULO).first(),
                usuario=current_user,
                descripcion=safe_message(f"Editado Servicio: {cit_servicio.descripcion}"),
                url=url_for("cit_servicios.detail", cit_servicio_id=cit_servicio.id),
            )
            bitacora.save()
            flash(bitacora.descripcion, "success")
            return redirect(bitacora.url)
    # Llenar los campos del formulario
    form.cit_categoria_nombre.data = cit_servicio.cit_categoria.nombre
    form.clave.data = cit_servicio.clave
    form.descripcion.data = cit_servicio.descripcion
    form.duracion.data = cit_servicio.duracion
    form.documentos_limite.data = cit_servicio.documentos_limite
    form.desde.data = cit_servicio.desde
    form.hasta.data = cit_servicio.hasta
    form.dias_habiles.data = _conversion_dias_habiles_numero_letra(cit_servicio.dias_habiles)
    # Entregar
    return render_template(
        "cit_servicios/edit.jinja2",
        form=form,
        cit_servicio=cit_servicio,
    )


def _conversion_dias_habiles_letra_numero(texto: str):
    """Regresa la conversión de días en letra a número"""
    if texto == "" or texto is None:
        return None

    resultado = ""
    if "LUNES" in texto:
        resultado = "0"
    if "MARTES" in texto:
        resultado += "1"
    if "MIERCOLES" in texto:
        resultado += "2"
    if "JUEVES" in texto:
        resultado += "3"
    if "VIERNES" in texto:
        resultado += "4"

    return resultado


def _conversion_dias_habiles_numero_letra(texto: str):
    """Regresa la conversión de días de número a letra"""
    if texto == "" or texto is None:
        return "LUNES, MARTES, MIERCOLES, JUEVES, VIERNES, "

    resultado = ""
    if "0" in texto:
        resultado = "LUNES, "
    if "1" in texto:
        resultado += "MARTES, "
    if "2" in texto:
        resultado += "MIERCOLES, "
    if "3" in texto:
        resultado += "JUEVES, "
    if "4" in texto:
        resultado += "VIERNES, "

    return resultado


@cit_servicios.route("/cit_servicios/eliminar/<int:cit_servicio_id>")
@permission_required(MODULO, Permiso.MODIFICAR)
def delete(cit_servicio_id):
    """Eliminar Servicio"""
    cit_servicio = CitServicio.query.get_or_404(cit_servicio_id)
    if cit_servicio.estatus == "A":
        cit_servicio.delete()
        bitacora = Bitacora(
            modulo=Modulo.query.filter_by(nombre=MODULO).first(),
            usuario=current_user,
            descripcion=safe_message(f"Eliminado Servi {cit_servicio.descripcion}"),
            url=url_for("cit_servicios.detail", cit_servicio_id=cit_servicio.id),
        )
        bitacora.save()
        flash(bitacora.descripcion, "success")
    return redirect(url_for("cit_servicios.detail", cit_servicio_id=cit_servicio.id))


@cit_servicios.route("/cit_servicios/recuperar/<int:cit_servicio_id>")
@permission_required(MODULO, Permiso.MODIFICAR)
def recover(cit_servicio_id):
    """Recuperar Servicio"""
    cit_servicio = CitServicio.query.get_or_404(cit_servicio_id)
    if cit_servicio.estatus == "B":
        cit_servicio.recover()
        bitacora = Bitacora(
            modulo=Modulo.query.filter_by(nombre=MODULO).first(),
            usuario=current_user,
            descripcion=safe_message(f"Recuperado Servicio {cit_servicio.descripcion}"),
            url=url_for("cit_servicios.detail", cit_servicio_id=cit_servicio.id),
        )
        bitacora.save()
        flash(bitacora.descripcion, "success")
    return redirect(url_for("cit_servicios.detail", cit_servicio_id=cit_servicio.id))

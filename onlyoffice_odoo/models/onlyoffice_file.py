# Copyright (C) 2026 Ascensio System SIA

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.onlyoffice_odoo.utils import file_utils

DOCUMENT_TYPES = [
    ("word", "Document"),
    ("cell", "Spreadsheet"),
    ("slide", "Presentation"),
    ("pdf", "PDF Form"),
]

DEFAULT_EXTENSIONS = {
    "word": "docx",
    "cell": "xlsx",
    "slide": "pptx",
    "pdf": "pdf",
}


class OnlyofficeFile(models.Model):
    _name = "onlyoffice.file"
    _description = "ONLYOFFICE File"
    _order = "last_edit_date desc, id desc"

    attachment_id = fields.Many2one("ir.attachment", required=True, ondelete="cascade", index=True, readonly=True)
    name = fields.Char(related="attachment_id.name", store=True, readonly=False, required=True)
    document_type = fields.Selection(DOCUMENT_TYPES, required=True, index=True)
    extension = fields.Char(compute="_compute_extension")
    file_size = fields.Integer(related="attachment_id.file_size")
    user_id = fields.Many2one("res.users", "Owner", default=lambda self: self.env.user, index=True)
    last_edit_date = fields.Datetime("Last Edited", default=fields.Datetime.now, readonly=True)
    last_edit_uid = fields.Many2one("res.users", "Last Edited By", default=lambda self: self.env.user, readonly=True)

    @api.depends("name")
    def _compute_extension(self):
        for file in self:
            name = file.name or ""
            file.extension = file_utils.get_file_ext(name).upper() if "." in name else False

    @api.model
    def _append_extension(self, name, extension):
        name = (name or "").strip()
        if not name:
            raise UserError(_("Please enter a file name."))
        if not name.lower().endswith(f".{extension}"):
            name = f"{name}.{extension}"
        return name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("attachment_id"):
                # an existing file, e.g. from another app: keep its content and its owner record
                vals.setdefault("name", self.env["ir.attachment"].browse(vals["attachment_id"]).name)
                continue

            document_type = vals.get("document_type") or self.env.context.get("default_document_type")
            if document_type not in DEFAULT_EXTENSIONS:
                raise UserError(_("Unknown document type: %(type)s", type=document_type))

            name = vals.pop("name", None)
            attachment_vals = {}
            if vals.get("raw"):
                attachment_vals["raw"] = vals.pop("raw")
                if file_utils.get_file_type(name or "") != document_type:
                    raise UserError(_("The file %(name)s does not match this app.", name=name))
            else:
                vals.pop("raw", None)
                extension = DEFAULT_EXTENSIONS[document_type]
                name = self._append_extension(name or _("New"), extension)
                attachment_vals["raw"] = file_utils.get_default_file_template(self.env.user.lang or "en_US", extension)
                attachment_vals["mimetype"] = file_utils.get_mime_by_ext(extension)

            attachment_vals["name"] = name
            vals["attachment_id"] = self._create_attachment(attachment_vals, document_type).id
            vals["name"] = name
            vals["document_type"] = document_type

        files = super().create(vals_list)
        for file in files:
            # attachments created for the file belong to it, those of other records are left alone
            if not file.attachment_id.res_model:
                file.attachment_id.write({"res_model": self._name, "res_id": file.id})
        return files

    @api.model
    def _create_attachment(self, attachment_vals, document_type):
        """Store the content of a new file, hook to keep it somewhere else (e.g. in Documents)."""
        return self.env["ir.attachment"].create(attachment_vals)

    def write(self, vals):
        if "name" not in vals:
            return super().write(vals)

        vals = dict(vals)
        name = vals.pop("name")
        res = super().write(vals) if vals else True
        for file in self:
            extension = file_utils.get_file_ext(file.attachment_id.name)
            file.attachment_id.name = self._append_extension(name, extension)
        return res

    def action_open_editor(self):
        self.ensure_one()
        # Always inside the web client, so the breadcrumbs lead back to the file list.
        return {
            "type": "ir.actions.client",
            "tag": "onlyoffice_editor",
            "name": self.name,
            "target": "current",
            "params": {"attachment_id": self.attachment_id.id},
        }

    def action_download(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self.attachment_id.id}?download=true",
            "target": "download",
        }

    def _action_open_create_wizard(self, mode):
        return {
            "type": "ir.actions.act_window",
            "name": _("Upload File") if mode == "upload" else _("New File"),
            "res_model": "onlyoffice.file.create",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_mode": mode,
                "default_document_type": self.env.context.get("default_document_type"),
            },
        }

    def action_create_file(self):
        return self._action_open_create_wizard("new")

    def action_upload_file(self):
        return self._action_open_create_wizard("upload")

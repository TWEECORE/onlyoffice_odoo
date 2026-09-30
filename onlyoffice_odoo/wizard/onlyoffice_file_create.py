# Copyright (C) 2026 Ascensio System SIA

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.onlyoffice_odoo.models.onlyoffice_file import DOCUMENT_TYPES
from odoo.addons.onlyoffice_odoo.utils import file_utils, format_utils


class OnlyofficeFileCreate(models.TransientModel):
    _name = "onlyoffice.file.create"
    _description = "Create ONLYOFFICE File"

    mode = fields.Selection([("new", "New"), ("upload", "Upload")], default="new", required=True)
    document_type = fields.Selection(DOCUMENT_TYPES, required=True)
    name = fields.Char()
    file = fields.Binary(attachment=False)
    filename = fields.Char()
    allowed_formats = fields.Char(compute="_compute_allowed_formats")

    @api.depends("document_type")
    def _compute_allowed_formats(self):
        for wizard in self:
            wizard.allowed_formats = ", ".join(
                f".{supported_format.name}"
                for supported_format in format_utils.get_supported_formats()
                if supported_format.type == wizard.document_type
            )

    def action_create(self):
        self.ensure_one()
        vals = {"document_type": self.document_type}
        if self.mode == "upload":
            if not self.file:
                raise UserError(_("Please select a file to upload."))
            filename = self.filename or self.file.filename or ""
            if file_utils.get_file_type(filename) != self.document_type:
                raise UserError(
                    _(
                        "The file %(name)s cannot be stored here. Allowed formats: %(formats)s",
                        name=filename,
                        formats=self.allowed_formats,
                    )
                )
            vals.update(name=filename, raw=self.file)
        else:
            vals["name"] = self.name

        return self.env["onlyoffice.file"].create(vals).action_open_editor()

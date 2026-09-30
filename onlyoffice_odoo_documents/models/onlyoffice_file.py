# Copyright (C) 2026 Ascensio System SIA

from odoo import api, fields, models

from odoo.addons.onlyoffice_odoo.utils import file_utils

# Documents folder of each app, the app shows the files of its folder
FOLDER_XMLIDS = {
    "word": "onlyoffice_odoo_documents.documents_folder_word",
    "cell": "onlyoffice_odoo_documents.documents_folder_cell",
    "slide": "onlyoffice_odoo_documents.documents_folder_slide",
    "pdf": "onlyoffice_odoo_documents.documents_folder_pdf",
}


class OnlyofficeFile(models.Model):
    _inherit = "onlyoffice.file"

    document_id = fields.Many2one(
        "documents.document", compute="_compute_document_id", store=True, index="btree_not_null"
    )

    @api.depends("attachment_id.document_ids")
    def _compute_document_id(self):
        for file in self:
            file.document_id = file.attachment_id.document_ids[:1]

    @api.model
    def _get_documents_folders(self):
        """Return {document_type: folder} for the folders that still exist."""
        folders = {}
        for document_type, xmlid in FOLDER_XMLIDS.items():
            folder = self.env.ref(xmlid, raise_if_not_found=False)
            if folder and folder.active:
                folders[document_type] = folder
        return folders

    @api.model
    def get_documents_folder_ids(self):
        return {document_type: folder.id for document_type, folder in self._get_documents_folders().items()}

    @api.model
    def _create_attachment(self, attachment_vals, document_type):
        folder = self._get_documents_folders().get(document_type)
        if not folder:
            return super()._create_attachment(attachment_vals, document_type)
        document = (
            self.env["documents.document"]
            .with_context(onlyoffice_skip_file_sync=True)
            .create({**attachment_vals, "folder_id": folder.id})
        )
        return document.attachment_id

    def write(self, vals):
        res = super().write(vals)
        if "name" in vals and not self.env.context.get("onlyoffice_skip_file_sync"):
            for file in self.filtered("document_id"):
                file.document_id.with_context(onlyoffice_skip_file_sync=True).name = file.name
        return res

    def unlink(self):
        documents = self.document_id
        res = super().unlink()
        if not self.env.context.get("onlyoffice_skip_file_sync"):
            # deleting in the app sends the file to the trash of Documents, where it can be restored
            documents.filtered("active").action_archive()
        return res

    @api.model
    def _link_existing_files_to_documents(self):
        """Move the files created before Documents was connected into the folders of their app."""
        folders = self._get_documents_folders()
        for file in self.sudo().search([("document_id", "=", False)]):
            folder = folders.get(file.document_type)
            if not folder:
                continue
            document = (
                self.env["documents.document"]
                .sudo()
                .with_context(onlyoffice_skip_file_sync=True)
                .create(
                    {
                        "attachment_id": file.attachment_id.id,
                        "folder_id": folder.id,
                        "owner_id": file.user_id.id,
                    }
                )
            )
            # the content now belongs to the document, like any file uploaded in Documents
            document.write({"res_model": False, "res_id": False})


class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    @api.model_create_multi
    def create(self, vals_list):
        documents = super().create(vals_list)
        if not self.env.context.get("onlyoffice_skip_file_sync"):
            documents._onlyoffice_sync_files()
        return documents

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("onlyoffice_skip_file_sync"):
            if {"folder_id", "active", "attachment_id"} & set(vals):
                self._onlyoffice_sync_files()
            elif "name" in vals:
                self._onlyoffice_sync_file_names()
        return res

    def unlink(self):
        files = self.env["onlyoffice.file"].sudo().search([("document_id", "in", self.ids)])
        files.with_context(onlyoffice_skip_file_sync=True).unlink()
        return super().unlink()

    def _onlyoffice_sync_files(self):
        """Make the ONLYOFFICE apps show exactly the active files of their folders."""
        Files = self.env["onlyoffice.file"].sudo().with_context(onlyoffice_skip_file_sync=True)
        type_by_folder = {folder.id: document_type for document_type, folder in Files._get_documents_folders().items()}
        for document in self.with_context(active_test=False):
            attachment = document.attachment_id
            if document.type != "binary" or not attachment:
                continue
            document_type = type_by_folder.get(document.folder_id.id)
            belongs_to_app = (
                document_type
                and document.active
                and file_utils.get_file_type(attachment.name or document.name or "") == document_type
            )
            files = Files.search([("attachment_id", "=", attachment.id)])
            if belongs_to_app and not files:
                Files.create(
                    {
                        "attachment_id": attachment.id,
                        "document_type": document_type,
                        "user_id": document.owner_id.id or self.env.user.id,
                    }
                )
            elif belongs_to_app:
                files.filtered(lambda f, t=document_type: f.document_type != t).write({"document_type": document_type})
            elif files:
                files.unlink()

    def _onlyoffice_sync_file_names(self):
        files = self.env["onlyoffice.file"].sudo().search([("document_id", "in", self.ids)])
        for file in files.with_context(onlyoffice_skip_file_sync=True):
            document = file.document_id.with_context(onlyoffice_skip_file_sync=True)
            if document.name and document.name != file.name:
                file.name = document.name
                # the app keeps the extension, so the document may need it back
                if document.name != file.name:
                    document.name = file.name

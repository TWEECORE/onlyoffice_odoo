/** @odoo-module **/
// Copyright (C) 2026 Ascensio System SIA

import { DocumentsKanbanRecord } from "@documents/views/kanban/documents_kanban_model"
import { DocumentsListModel } from "@documents/views/list/documents_list_model"
import { patch } from "@web/core/utils/patch"

// Office files open in their ONLYOFFICE app instead of the preview of Documents.
// Text formats (txt, csv, ...) keep the text preview of Documents, and PDFs keep the PDF viewer
// (with its split tool) unless they are in the folder of the PDF Forms app.
const APP_TYPES = ["word", "cell", "slide"]

let formatsPromise
const loadFormats = () => {
  formatsPromise ||= fetch("/onlyoffice_odoo/static/assets/document_formats/onlyoffice-docs-formats.json")
    .then((response) => response.json())
    .catch((error) => {
      console.error("Error loading formats data:", error)
      return []
    })
  return formatsPromise
}
loadFormats()

let folderIdsPromise
const loadFolderIds = (orm) => {
  folderIdsPromise ||= orm.call("onlyoffice.file", "get_documents_folder_ids").catch(() => ({}))
  return folderIdsPromise
}

async function getOnlyofficeAppType(record) {
  const target = record.shortcutTarget || record
  const name = target.data.name || target.data.display_name || ""
  if (target.data.type !== "binary" || !name.includes(".")) {
    return false
  }
  const extension = name.split(".").pop().toLowerCase()
  const format = (await loadFormats()).find((f) => f.name === extension)
  if (!format?.actions?.some((a) => a === "view" || a === "edit")) {
    return false
  }
  if (APP_TYPES.includes(format.type) && !format.mime?.some((mime) => mime.startsWith("text/"))) {
    return format.type
  }
  if (format.type === "pdf") {
    const folderIds = await loadFolderIds(record.model.orm)
    return target.data.folder_id?.id === folderIds.pdf && "pdf"
  }
  return false
}

const openInOnlyofficeAppPatch = {
  async onClickPreview(ev) {
    if (!this.isRequest() && !navigator.userAgent.includes("AscDesktopEditor")) {
      ev?.stopPropagation()
      ev?.preventDefault()
      const documentType = await getOnlyofficeAppType(this)
      if (documentType) {
        const target = this.shortcutTarget || this
        return this.model.action.doAction({
          params: { document_id: target.resId, document_type: documentType, name: target.data.name },
          tag: "onlyoffice_open_in_app",
          type: "ir.actions.client",
        })
      }
    }
    return super.onClickPreview(...arguments)
  },
}

patch(DocumentsKanbanRecord.prototype, openInOnlyofficeAppPatch)
patch(DocumentsListModel.Record.prototype, openInOnlyofficeAppPatch)

/** @odoo-module **/
// Copyright (C) 2026 Ascensio System SIA

import { usePlugin } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks"
import { KanbanRecord } from "@web/views/kanban/kanban_record"
import { ActionManagerPlugin } from "@web/webclient/actions/action_plugin";

export class OnlyofficeKanbanRecord extends KanbanRecord {
  setup() {
    super.setup(...arguments)
    this.orm = useService("orm")
    this.actionService = usePlugin(ActionManagerPlugin)
  }

  /**
   * @override
   */
  async onGlobalClick() {
    return this.editTemplate()
  }

  async editTemplate() {
    const action = {
      params: {
        attachment_id: this.props.record.data.attachment_id.id,
        id: this.props.record.data.id,
        template_model_model: this.props.record.data.template_model_model,
      },
      tag: "onlyoffice_template_editor",
      target: "current",
      type: "ir.actions.client",
    }
    return this.actionService.doAction(action, { props: this.props.record.data })
  }
}

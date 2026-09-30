/** @odoo-module **/
// Copyright (C) 2026 Ascensio System SIA

import { Component, onMounted, onWillUnmount, proxy, useProps } from "@odoo/owl"
import { cookie } from "@web/core/browser/cookie"
import { router } from "@web/core/browser/router"
import { _t } from "@web/core/l10n/translation"
import { rpc } from "@web/core/network/rpc"
import { registry } from "@web/core/registry"
import { useService } from "@web/core/utils/hooks"
import { useSubEnv } from "@web/owl2/utils"
import { useSetupAction } from "@web/search/action_hook"
import { Layout } from "@web/search/layout"
import { getDefaultConfig } from "@web/views/view"
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin"

export class DocumentsAction extends Component {
  static components = { Layout }
  props = useProps(standardActionServiceProps)

  setup() {
    super.setup()
    useSubEnv({
      config: {
        ...getDefaultConfig(),
        ...this.env.config,
      },
    })
    useSetupAction()
    this.state = proxy({ title: this.props.action.name || "" })
    this.rpc = rpc
    this.orm = useService("orm")
    this.actionService = useService("action")
    this.menuService = useService("menu")
    this.ui = useService("ui")
    this.router = router
    this.onNavbarToggleClick = this.onNavbarToggleClick.bind(this)
    this.onNavbarToggleHover = this.onNavbarToggleHover.bind(this)

    onMounted(async () => {
      this.showOnlyofficeApp()
      this.useNavbarToggleAsBack()
      try {
        const args = {}
        if (this.props.action.params.document_id) {
          const document_id = this.props.action.params.document_id
          args.document_id = document_id
          this.router.pushState({ document_id: document_id, document_type: this.props.action.params.document_type })
        } else if (this.props.action.params.attachment_id) {
          const attachment_id = this.props.action.params.attachment_id
          args.attachment_id = attachment_id
          this.router.pushState({ attachment_id: attachment_id })
        }
        const response = await this.rpc("/onlyoffice/editor/get_config", args)
        if (response.docTitle) {
          this.state.title = response.docTitle
          this.env.config.setDisplayName(response.docTitle)
        }
        const config = response.editorConfig
        const theme = cookie.get("color_scheme")
        config.editorConfig.customization = {
          ...config.editorConfig.customization,
          uiTheme: theme ? `default-${theme}` : "default-light",
          // the title bar of the editor is replaced by the Odoo navbar, which shows the file name
          compactHeader: true,
          toolbarHideFileName: true,
        }
        this.config = config

        this.docApiJS = response.docApiJS
        if (!window.DocsAPI) {
          await this.loadDocsAPI(this.docApiJS)
        }
        if (window.DocsAPI) {
          window.docEditor = new DocsAPI.DocEditor("doceditor", this.config)
        } else {
          document.getElementById("error").classList.remove("d-none")
          throw new Error("window.DocsAPI is null")
        }
      } catch (error) {
        console.error("onMounted Editor error:", error)
        document.getElementById("error")?.classList.remove("d-none")
      }
    })

    onWillUnmount(() => {
      // Leaving the action through the breadcrumbs must not keep the editor (and its session) alive.
      window.docEditor?.destroyEditor()
      window.docEditor = undefined
      this.restoreNavbarToggle()
      this.restorePreviousApp()
    })
  }

  /**
   * A file opened from another app (e.g. a presentation in Documents) is shown in its ONLYOFFICE app,
   * while the breadcrumbs still lead back to where it was opened from.
   */
  showOnlyofficeApp() {
    const documentType = this.props.action.params.document_type
    const app =
      documentType &&
      this.menuService.getApps().find((menu) => menu.xmlid === `onlyoffice_odoo.menu_onlyoffice_${documentType}`)
    const currentApp = this.menuService.getCurrentApp()
    if (app && app.id !== currentApp?.id) {
      this.previousApp = currentApp
      this.shownApp = app
      this.menuService.setCurrentMenu(app)
    }
  }

  restorePreviousApp() {
    // unless another app was opened meanwhile
    if (this.previousApp && this.menuService.getCurrentApp()?.id === this.shownApp.id) {
      this.menuService.setCurrentMenu(this.previousApp)
    }
  }

  /**
   * In the editor, the "‹" of the navbar (normally the home menu) goes back to where the file was opened from.
   */
  useNavbarToggleAsBack() {
    document.addEventListener("click", this.onNavbarToggleClick, true)
    // the navbar may be rendered again (e.g. for the app of the file), so the title is set when hovering
    document.addEventListener("mouseover", this.onNavbarToggleHover, true)
  }

  onNavbarToggleHover(ev) {
    if (ev.target.closest?.(".o_main_navbar .o_menu_toggle")) {
      this.updateNavbarToggleTitle()
    }
  }

  get navbarToggle() {
    return document.querySelector(".o_main_navbar .o_menu_toggle")
  }

  updateNavbarToggleTitle() {
    const toggle = this.navbarToggle
    if (toggle && this.previousBreadcrumb && !this.ui.isSmall) {
      this.navbarToggleTitle ??= toggle.getAttribute("title")
      toggle.setAttribute("title", this.backTooltip)
      toggle.setAttribute("aria-label", this.backTooltip)
    }
  }

  restoreNavbarToggle() {
    document.removeEventListener("click", this.onNavbarToggleClick, true)
    document.removeEventListener("mouseover", this.onNavbarToggleHover, true)
    const toggle = this.navbarToggle
    if (toggle && this.navbarToggleTitle) {
      toggle.setAttribute("title", this.navbarToggleTitle)
      toggle.setAttribute("aria-label", this.navbarToggleTitle)
    }
  }

  onNavbarToggleClick(ev) {
    // on small screens the toggle opens the app menu, the back button of the navbar is used instead
    if (this.ui.isSmall || !this.previousBreadcrumb || !ev.target.closest(".o_main_navbar .o_menu_toggle")) {
      return
    }
    ev.preventDefault()
    ev.stopImmediatePropagation()
    this.onBackClick()
  }

  get previousBreadcrumb() {
    return this.env.config.breadcrumbs?.at(-2)
  }

  get backTooltip() {
    return _t("Back to “%s”", this.previousBreadcrumb?.name || "")
  }

  onBackClick() {
    this.env.config.historyBack()
  }

  async loadDocsAPI(DocsAPI) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script")
      script.src = DocsAPI
      script.onload = resolve
      script.onerror = reject
      document.body.appendChild(script)
      this.script = script
    })
  }
}

DocumentsAction.template = "onlyoffice_odoo.Editor"

registry.category("actions").add("onlyoffice_editor", DocumentsAction, { force: true })

/**
 * Opens a file in the ONLYOFFICE app of its type (Text, Spreadsheets, ...): the navbar shows that app,
 * going back still leads to where the file was opened from.
 * params: document_type, name and either attachment_id or document_id
 */
function openInOnlyofficeApp(env, action) {
  const { name, ...params } = action.params
  return { name, params, tag: "onlyoffice_editor", target: "current", type: "ir.actions.client" }
}

registry.category("actions").add("onlyoffice_open_in_app", openInOnlyofficeApp)

/** @odoo-module **/

import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";

// Keeps Odoo's own top bar / app switcher / breadcrumb visible (this is a genuine client
// action, not a full-page navigation away from the backend) and shows the dashboard
// controller's own page — with its own colors/layout/animation — in an iframe below it.
class BsiSalonDashboardClientAction extends Component {
    static template = xml`
        <iframe src="/salon/dashboard"
                style="width:100%;height:100%;border:0;display:block;background:#fff;"/>
    `;
}

registry.category("actions").add("bsi_salon_dashboard_client", BsiSalonDashboardClientAction);

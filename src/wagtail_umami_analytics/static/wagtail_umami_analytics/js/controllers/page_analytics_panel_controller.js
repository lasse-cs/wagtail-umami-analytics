class PageAnalyticsPanelController extends window.StimulusModule.Controller {
    static targets = [ "stats", "error", "pageviews", "visitors", "visits", "bounces" ];

    update(event) {
        const stats = event.detail.json["stats"];
        this.pageviewsTarget.textContent = stats["pageviews"];
        this.visitorsTarget.textContent = stats["visitors"];
        this.visitsTarget.textContent = stats["visits"];
        this.bouncesTarget.textContent = stats["bounces"];
        this.errorTarget.hidden = true;
        this.statsTarget.hidden = false;
    }

    showError() {
        this.statsTarget.hidden = true;
        this.errorTarget.hidden = false;
    }
}

window.wagtail.app.register("page-analytics-panel", PageAnalyticsPanelController);

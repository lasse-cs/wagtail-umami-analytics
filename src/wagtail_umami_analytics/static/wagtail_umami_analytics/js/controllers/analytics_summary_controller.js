class AnalyticsSummaryController extends window.StimulusModule.Controller {
    static targets = [ "activeUsers", "pageviews", "visits", "visitors", "bounces" ];
    static values = { activeUsers: Number, pageviews: Number, visits: Number, visitors: Number, bounces: Number };

    updateActiveUsers(event) {
        this.activeUsersValue = event.detail.json["active_users"];
    }

    updateStats(event) {
        const stats = event.detail.json["stats"];
        this.pageviewsValue = stats["pageviews"];
        this.visitsValue = stats["visits"];
        this.visitorsValue = stats["visitors"];
        this.bouncesValue = stats["bounces"];
    }

    onFailure() {
        document.dispatchEvent(
            new CustomEvent('w-messages:add', {
                detail: { text: 'Failed to load summary data', type: 'error', clear: true },
            }),
        );
    }

    activeUsersValueChanged(value, previousValue) {
        if (previousValue === undefined) value = "-";
        this.activeUsersTargets.forEach(element => element.textContent = value);
    }

    pageviewsValueChanged(value, previousValue) {
        if (previousValue === undefined) value = "-";
        this.pageviewsTargets.forEach(element => element.textContent = value);
    }

    visitorsValueChanged(value, previousValue) {
        if (previousValue === undefined) value = "-";
        this.visitorsTargets.forEach(element => element.textContent = value);
    }

    visitsValueChanged(value, previousValue) {
        if (previousValue === undefined) value = "-";
        this.visitsTargets.forEach(element => element.textContent = value);
    }

    bouncesValueChanged(value, previousValue) {
        if (previousValue === undefined) value = "-";
        this.bouncesTargets.forEach(element => element.textContent = value);
    }
}

window.wagtail.app.register("analytics-summary", AnalyticsSummaryController);
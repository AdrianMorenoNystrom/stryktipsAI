import { DatePipe } from "./time";
import { Component, inject } from "@angular/core";

import { RouterLink, RouterLinkActive, RouterOutlet } from "@angular/router";
import { Store } from "./store";
import { DrawerComponent } from "./components/drawer.component";
import { LiveCouponComponent } from "./components/live-coupon.component";

@Component({
  selector: "app-root",
  standalone: true,
  imports: [
    DatePipe,
    RouterLink,
    RouterLinkActive,
    RouterOutlet,
    DrawerComponent,
    LiveCouponComponent,
  ],
  template: `
    <a href="#main" class="skip-link">Hoppa till innehåll</a>
    <header class="topbar">
      <div class="nav-inner">
        <a routerLink="/overview" class="brand"
          ><span class="brand-mark" aria-hidden="true">1<span>X</span>2</span
          ><span>STRYKTIPSET <b>AI</b></span></a
        >
        <nav aria-label="Huvudnavigation">
          @for (item of navigation; track item.path) {
            <a
              [routerLink]="item.path"
              routerLinkActive="active"
              ariaCurrentWhenActive="page"
              >{{ item.label }}</a
            >
          }
        </nav>
        <span class="nav-week">VECKA {{ store.coupon()?.week ?? "—" }}</span>
      </div>
    </header>
    <main id="main" tabindex="-1">
      <div class="week-header">
        <div>
          <p class="eyebrow">DIN RAD, MED EFTERTANKE</p>
          <h1>
            Stryktipset
            <span
              >·
              {{
                store.dataMode() === "live"
                  ? "Omgång " + (store.live()?.draw?.draw_number ?? "—")
                  : "Vecka " + (store.coupon()?.week ?? "—")
              }}</span
            >
          </h1>
          <p class="muted">
            {{
              (store.dataMode() === "live"
                ? store.live()?.draw?.draw_date
                : store.coupon()?.date
              ) | date: "yyyy-MM-dd"
            }}
            <span class="date-divider">/</span> 13 matcher · 1 X 2
            @if (
              store.dataMode() === "live" && store.live()?.draw?.sales_close_at;
              as close
            ) {
              <br />Spelstopp {{ close | date: "dd/MM HH:mm" }}
            }
          </p>
        </div>
        <div class="data-status">
          @if (store.dataMode() === "live" && store.live()?.draw) {
            <span class="tag live-label">LIVE DATA</span>
          } @else if (store.coupon()?.demo) {
            <span class="demo-label">DEMO DATA</span>
          } @else if (store.coupon()) {
            <span class="tag">MANUELL KUPONG</span>
          } @else {
            <span class="tag">DATA SAKNAS</span>
          }
          <small
            >{{
              store.dataMode() === "live"
                ? "Aktuell kupong · Svenska Spel"
                : store.coupon()?.demo
                  ? "Exempelmatcher, odds och streck"
                  : "Egen inmatning"
            }}<br />
            @if (store.analysis(); as result) {
              Uppdaterad {{ result.analyzedAt | date: "HH:mm" }}
            }
            @if (store.dataMode() === "live") {
              <br />Svenska Folket hämtat
              {{ store.live()?.draw?.retrieved_at | date: "HH:mm" }}
            }
          </small>
        </div>
      </div>
      @if (store.live()?.stale) {
        <p class="notice warning" role="status">
          Live-data kunde inte uppdateras. Visar senast sparad data från
          {{ store.live()?.draw?.retrieved_at | date: "dd/MM HH:mm" }}.
        </p>
      }
      <div class="coupon-actions">
        <button
          (click)="store.loadCurrent(undefined, true)"
          [disabled]="store.loading()"
        >
          Uppdatera
        </button>
        <details
          class="source-settings"
          [open]="store.live()?.draw && !store.live()?.analysis_ready"
        >
          <summary>Kupongval och datakällor</summary>
          <app-live-coupon />
        </details>
      </div>
      @if (store.error()) {
        <div class="notice error" role="alert">
          <p>{{ store.error() }}</p>
          <button (click)="retry()">Försök igen</button>
          @if (store.analysis()) {
            <p class="small">
              Tidigare analys visas. Den senaste ändringen kunde inte beräknas.
            </p>
          }
        </div>
      }
      @if (store.notice()) {
        <p class="notice" role="status">{{ store.notice() }}</p>
      }
      @if (store.fallbackCount()) {
        <p class="notice warning" role="status">
          Marknadsfallback används för {{ store.fallbackCount() }} av 13
          matcher. Orsak finns i respektive matchanalys.
        </p>
      }
      @if (store.loading()) {
        <section
          class="loading-state"
          aria-label="Analyserar kupong"
          aria-busy="true"
        >
          <div class="skeleton"></div>
          <div class="skeleton short"></div>
          <span class="small muted">Beräknar sannolikheter och system…</span>
        </section>
      }
      <router-outlet />
      <footer class="page-footer">
        <span
          >Oberoende analysverktyg. Ej anslutet till eller godkänt av Svenska
          Spel.</span
        ><span
          >Sannolikhet är inte ett löfte. Spelvärde är inte garanterad
          vinst.</span
        >
      </footer>
    </main>
    <nav class="bottom-nav" aria-label="Mobilnavigation">
      @for (item of navigation; track item.path) {
        <a
          [routerLink]="item.path"
          routerLinkActive="active"
          ariaCurrentWhenActive="page"
          ><span aria-hidden="true">{{ item.icon }}</span
          >{{ item.label }}</a
        >
      }
    </nav>
    @if (store.selectedMatch(); as match) {
      <app-drawer [match]="match" />
    }
  `,
})
export class AppComponent {
  readonly store = inject(Store);
  readonly navigation = [
    { path: "/overview", label: "Kupongen", icon: "▦" },
    { path: "/analysis", label: "Analys", icon: "↗" },
    { path: "/history", label: "Historik", icon: "◷" },
  ];
  constructor() {
    void this.store.initialize();
  }
  retry(): void {
    if (this.store.coupon()) void this.store.analyze();
    else void this.store.initialize();
  }
}

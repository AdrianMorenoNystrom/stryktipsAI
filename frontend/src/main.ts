import { bootstrapApplication } from "@angular/platform-browser";
import { provideHttpClient, withInterceptors } from "@angular/common/http";
import { provideRouter, withHashLocation } from "@angular/router";
import { LOCALE_ID } from "@angular/core";
import { registerLocaleData } from "@angular/common";
import sv from "@angular/common/locales/sv";
import { deployment } from "./deployment";
import { AppComponent } from "./app/app.component";
import { OverviewComponent } from "./app/pages/overview.component";
import { CouponComponent } from "./app/pages/coupon.component";
registerLocaleData(sv);

bootstrapApplication(AppComponent, {
  providers: [
    { provide: LOCALE_ID, useValue: "sv-SE" },
    provideHttpClient(
      withInterceptors([
        (req, next) =>
          next(
            req.url.startsWith("/api/")
              ? req.clone({ url: deployment.apiBaseUrl + req.url })
              : req,
          ),
      ]),
    ),
    provideRouter(
      [
        { path: "overview", component: OverviewComponent },
        { path: "coupon", component: CouponComponent },
        {
          path: "analysis",
          loadComponent: () =>
            import("./app/pages/analysis.component").then(
              (m) => m.AnalysisComponent,
            ),
        },
        {
          path: "history",
          loadComponent: () =>
            import("./app/pages/history.component").then(
              (m) => m.HistoryComponent,
            ),
        },
        { path: "**", redirectTo: "overview" },
      ],
      ...(deployment.hashRouting ? [withHashLocation()] : []),
    ),
  ],
}).catch(console.error);

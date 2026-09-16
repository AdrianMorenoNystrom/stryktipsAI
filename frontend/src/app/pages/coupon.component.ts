import { Component, inject, signal } from "@angular/core";
import { DecimalPipe } from "@angular/common";
import { Store } from "../store";
import { OUTCOMES } from "../models";
import { BudgetComponent } from "../components/budget.component";
import { CouponEditorComponent } from "../components/coupon-editor.component";

@Component({
  standalone: true,
  imports: [DecimalPipe, BudgetComponent, CouponEditorComponent],
  template: `
    <div class="section-line page-intro">
      <div>
        <p class="eyebrow">BYGG DITT SYSTEM</p>
        <h2>Din kupong</h2>
        <p class="muted">
          Modellens val är förvalda. Anpassa tecknen efter din egen analys.
        </p>
      </div>
      <button (click)="editing.set(!editing())">
        {{ editing() ? "Dölj inmatning" : "Redigera matcher, odds och streck" }}
      </button>
    </div>
    @if (editing()) {
      <app-coupon-editor (closed)="editing.set(false)" />
    }
    <section class="panel coupon-controls"><app-budget /></section>
    @if (store.analysis(); as analysis) {
      <div class="section-line">
        <p>
          {{ store.modified() ? "Manuellt ändrad" : "Modellens val" }}
          @if (store.modified()) {
            <span class="tag">EGET SYSTEM</span>
          }
        </p>
        <button (click)="store.reset()" [disabled]="!store.modified()">
          Återställ modellens val
        </button>
      </div>
      <div class="coupon-layout">
        <section class="panel builder" aria-label="Systemets tecken">
          @for (
            match of analysis.matches;
            track match.number;
            let index = $index
          ) {
            <div class="builder-row">
              <span class="match-number">{{ match.number }}</span>
              <div class="builder-teams">
                <strong>{{ match.homeTeam }} – {{ match.awayTeam }}</strong>
                <p class="small muted">
                  {{ store.probabilityLabel(match) }}:
                  {{ match.model.home * 100 | number: "1.0-0" }} /
                  {{ match.model.draw * 100 | number: "1.0-0" }} /
                  {{ match.model.away * 100 | number: "1.0-0" }}%<br />Folket:
                  {{ match.crowd.home * 100 | number: "1.0-0" }} /
                  {{ match.crowd.draw * 100 | number: "1.0-0" }} /
                  {{ match.crowd.away * 100 | number: "1.0-0" }}%
                </p>
              </div>
              <div class="sign-selector">
                @for (outcome of outcomes; track outcome.key) {
                  <button
                    [class.active]="
                      store.selections()[index].includes(outcome.sign)
                    "
                    [attr.aria-pressed]="
                      store.selections()[index].includes(outcome.sign)
                    "
                    [attr.aria-label]="
                      'Välj ' +
                      outcome.sign +
                      ' för ' +
                      match.homeTeam +
                      ' mot ' +
                      match.awayTeam
                    "
                    (click)="store.toggle(index, outcome.sign)"
                  >
                    {{ outcome.sign }}
                  </button>
                }
              </div>
              <button
                class="text-button"
                (click)="store.selectedMatch.set(match)"
                [attr.aria-label]="'Analys match ' + match.number"
              >
                ↗
              </button>
            </div>
          }
        </section>
        <aside class="panel price-panel" aria-live="polite">
          <p class="eyebrow">DITT SYSTEM</p>
          @if (store.costPending()) {
            <h2>Beräknar…</h2>
          } @else if (store.manualCost(); as cost) {
            <h2>{{ cost.cost | number: "1.0-2" }} kr</h2>
            <p>{{ cost.rowCount }} rader · {{ cost.costPerRow }} kr/rad</p>
            <dl class="comparison">
              <div>
                <dt>Spikar</dt>
                <dd>{{ cost.singles }}</dd>
              </div>
              <div>
                <dt>Halvgarderingar</dt>
                <dd>{{ cost.doubles }}</dd>
              </div>
              <div>
                <dt>Helgarderingar</dt>
                <dd>{{ cost.triples }}</dd>
              </div>
            </dl>
            @if (cost.cost > store.budget()) {
              <p class="notice warning">
                Ditt manuella system överstiger budgeten på
                {{ store.budget() }} kr.
              </p>
            }
          }
          <button
            class="primary"
            (click)="store.copy()"
            [disabled]="store.costPending() || !store.manualCost()"
          >
            Kopiera system
          </button>
          <p class="small muted">Ingen inlämning sker i appen.</p>
        </aside>
      </div>
    }
  `,
})
export class CouponComponent {
  readonly store = inject(Store);
  readonly editing = signal(false);
  readonly outcomes = OUTCOMES;
}

import { Component, inject } from "@angular/core";
import { DecimalPipe } from "@angular/common";
import { RouterLink } from "@angular/router";
import { Store } from "../store";
import { BudgetComponent } from "./budget.component";
import { InfoComponent } from "./info.component";
@Component({
  selector: "app-hero",
  standalone: true,
  imports: [DecimalPipe, RouterLink, BudgetComponent, InfoComponent],
  template: ` @if (store.analysis(); as analysis) {
    <section
      class="hero panel"
      aria-labelledby="optimal-heading"
      [attr.aria-busy]="store.loading()"
    >
      <p class="eyebrow">DIN KUPONG, MED EFTERTANKE</p>
      <h2 id="optimal-heading">
        Rekommenderat system
        <span>· {{ analysis.system.cost | number: "1.0-2" }} kr</span>
      </h2>
      <div class="optimal-grid">
        @for (selection of analysis.system.selections; track $index) {
          <button
            class="optimal-cell"
            (click)="store.selectedMatch.set(analysis.matches[$index])"
            [attr.aria-label]="
              'Match ' +
              ($index + 1) +
              ': ' +
              selection.join('') +
              '. Visa förklaring.'
            "
          >
            <small>{{ $index + 1 }}</small
            ><strong>{{ selection.join("") }}</strong>
          </button>
        }
      </div>
      <div class="system-stats">
        <span
          ><strong>{{ analysis.system.singles }}</strong> spikar</span
        >
        @if (analysis.system.doubles) {
          <span
            ><strong>{{ analysis.system.doubles }}</strong>
            halvgarderingar</span
          >
        }
        <span
          ><strong>{{ analysis.system.triples }}</strong> helgarderingar</span
        ><span
          >{{ analysis.system.rowCount }} rader ·
          {{ analysis.system.cost | number: "1.0-2" }} kr</span
        >
      </div>
      <div class="chance-summary">
        <div>
          <span class="field-caption"
            >BERÄKNAD CHANS ATT TÄCKA 13 RÄTT
            <app-info
              label="Förklara 13-rättschansen"
              text="Modellens uppskattning av sannolikheten att systemets val täcker alla 13 matchresultat, om matcherna behandlas som oberoende. Det är en uppskattning, inte en garanti."
          /></span>
          <strong
            >{{
              analysis.system.metrics.allCorrectProbability * 100
                | number: "1.2-2"
            }}
            %</strong
          ><span>
            ≈ 1 på
            {{
              store.oneIn(analysis.system.metrics.allCorrectProbability)
                | number: "1.0-0"
            }}</span
          >
        </div>
      </div>
      <app-budget />
      <div class="hero-footer">
        <button class="primary" (click)="store.copy()">Kopiera system</button
        ><a routerLink="/coupon" class="text-button">Anpassa tecken</a>
      </div>
      <details class="system-changes">
        <summary>Fördjupa: systemets underlag och ändringar</summary>
        <p>
          Spelvärde jämför vår sannolikhet med folkets streck. Det är inte samma
          sak som ekonomisk avkastning. Systemets jämförelseindex:
          {{ analysis.system.metrics.valueIndex | number: "1.2-2" }}.
        </p>
        @for (change of analysis.changes ?? []; track change.number) {
          <p>
            Match {{ change.number }}: {{ change.previous.join("") }} →
            {{ change.current.join("") }}
          </p>
        } @empty {
          <p>
            Inga registrerade teckenändringar mot förra analysen med samma
            budget och profil.
          </p>
        }
      </details>
    </section>
  }`,
})
export class HeroComponent {
  readonly store = inject(Store);
}

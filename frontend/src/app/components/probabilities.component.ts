import { Component, input } from "@angular/core";
import { DecimalPipe } from "@angular/common";
import { OUTCOMES, Probabilities } from "../models";
import { InfoComponent } from "./info.component";

@Component({
  selector: "app-probabilities",
  standalone: true,
  imports: [DecimalPipe, InfoComponent],
  template: `
    <div class="probability-row" [class.primary-probability]="primary()">
      <span
        >{{ label() }}
        @if (label() === "Svenska Folket") {
          <app-info
            label="Förklara Svenska Folket"
            text="Andelen av de inlämnade Stryktipsraderna som innehåller respektive tecken enligt Svenska Spels aktuella data."
          />
        } @else if (label() === "Vår sannolikhet") {
          <app-info
            label="Förklara vår sannolikhet"
            text="Vår uppskattning av 1/X/2 utifrån den angivna marknadskällan. Bookmakerkonsensus används när tillräckliga odds finns; alternativ källa märks som fallback."
          />
        }
      </span>
      @for (outcome of outcomes; track outcome.key) {
        <span
          ><small>{{ outcome.sign }}</small
          ><strong
            >{{ values()[outcome.key] * 100 | number: "1.0-1"
            }}<small>%</small></strong
          ></span
        >
      }
    </div>
  `,
})
export class ProbabilitiesComponent {
  readonly label = input.required<string>();
  readonly values = input.required<Probabilities>();
  readonly primary = input(false);
  readonly outcomes = OUTCOMES;
}

import { Component, input } from "@angular/core";
@Component({
  selector: "app-info",
  standalone: true,
  template: `<details class="inline-info">
    <summary [attr.aria-label]="label()">ⓘ</summary>
    <p>{{ text() }}</p>
  </details>`,
})
export class InfoComponent {
  readonly label = input("Förklaring");
  readonly text = input.required<string>();
}

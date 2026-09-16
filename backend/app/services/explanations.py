"""Plain Swedish, deterministic descriptions of actual probabilities and selections."""
from app.config import OUTCOMES, SIGNS


def explain(match, selection):
    probable=max(OUTCOMES,key=lambda k:match['model'][k])
    sign=SIGNS[OUTCOMES.index(probable)]
    delta=match['model'][probable]-match['crowd'][probable]
    prefix=f"{sign} är mest sannolikt: {match['model'][probable]*100:.0f} %, jämfört med Svenska Folkets {match['crowd'][probable]*100:.0f} %. "
    comparison='Tecknet är överstreckat i denna jämförelse. ' if delta < -.03 else 'Tecknet är understreckat i denna jämförelse. ' if delta > .03 else 'Bedömningen ligger nära Svenska Folkets streck. '
    if len(selection)==3:
        choice='Systemet täcker alla tre utfall i den här matchen.'
    elif len(selection)==2:
        choice=f"Systemet garderar med {''.join(selection)} inom din budget."
    elif selection[0]!=sign:
        choice=f"Systemet väljer spiken {selection[0]}, ett mindre sannolikt utfall, efter avvägningen mot strecken och budgeten."
    else:
        choice=f"Systemet väljer spiken {sign} inom din budget."
    return prefix+comparison+choice

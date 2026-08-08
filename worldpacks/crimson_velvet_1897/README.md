# The Crimson Velvet — 1897

Worldpack EPOS v3.1 ambientato sulla Riviera ligure nel 1897.

## Premessa

Il Crimson Velvet è un hotel-casinò Belle Époque costruito dentro una villa aristocratica. Un vecchio titolo di proprietà, un registro notarile scomparso e una rete di contrabbando d'arte minacciano la casa. Il protagonista entra come ospite e possibile investitore, ma non è obbligato ad acquistare nulla.

## Le quattro NPC

- Victoria Hale — proprietaria e direttrice. Arco: proprietà, autonomia, fiducia e futuro della casa.
- Stella — cantante e maîtresse de spectacle. Arco: carriera europea, ricatto reputazionale, indipendenza artistica.
- Maria — responsabile della casa e dell'archivio. Arco: lettere compromettenti, autorità professionale, etica della memoria.
- Luna — guida costiera e intermediaria informale. Arco: contrabbando, pescatori, registro scomparso, libertà personale.

Tutte sono adulte. Ogni relazione intima è separata da denaro, lavoro, protezione e obblighi professionali.

## Apertura

L'intro è deterministica e governata da Python:

1. il giocatore si presenta;
2. Victoria si presenta;
3. Victoria introduce Luna;
4. viene introdotta Maria;
5. viene introdotta Stella;
6. si apre il freeplay.

Durante l'intro eventi, iniziative autonome e avanzamento del tempo restano bloccati.

## Trama principale

La missione `mission_crimson_fate` richiede quattro fatti autorevoli:

- `title_dispute_discovered`
- `missing_register_recovered`
- `creditor_connection_resolved`
- `crimson_ownership_decision`

La decisione sulla proprietà può portare a sostegno di Victoria, acquisto equo, trust indipendente, restituzione di quote agli eredi o causa giudiziaria. Il Worldpack non assume quale sia la scelta corretta.

## Archi personali

### Victoria

Copia dell'atto → termini privati → autonomia personale → destino della casa → milestone adulto.

### Stella

Prova generale → lettera del critico → contratto europeo → scelta privata → milestone adulto.

### Maria

Inventario → lettera del creditore → destino delle lettere → riconoscimento professionale → milestone adulto.

### Luna

Passaggio nascosto → rete della cala → recupero del registro → scelta sui pescatori → milestone adulto.

## Fine campagna

`mission_crimson_legacy` richiede:

- `crimson_fate_resolved`
- `victoria_bond_complete`
- `stella_bond_complete`
- `maria_bond_complete`
- `luna_bond_complete`

Quando tutte sono vere Python imposta `campaign_complete`. L'evento epilogo permette comunque di continuare in freeplay.

## Tempo

Il mondo è open-ended. Gli schedule sono authorati per sette pattern giornalieri; il motore open-end mantiene una routine valida oltre il periodo iniziale senza imporre una chiusura narrativa.

## Visual

Il visual canon è 1897 Belle Époque: gaslight, velluto, mogano, abiti tardo-vittoriani, teatro privato, casinò, archivio e costa ligure. Outfit moderni e dispositivi moderni sono esclusi dal negative prompt e dall'Outfit Library.

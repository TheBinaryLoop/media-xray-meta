"""Deadpool (2016) trivia, English and German, each from a source read for this purpose.
Moments come from the transcript, the measured segments and the matched music cues."""
import json
from pathlib import Path

EN = 'https://en.wikipedia.org/wiki/Deadpool_(film)'
DE = 'https://de.wikipedia.org/wiki/Deadpool_(Film)#Comicvorlage_und_popkulturelle_Referenzen'

items = [
    # (from, to, sources, en, de, spoiler)
    (40.0, 146.0, [EN + '#Visual_effects'],
     'The opening titles travel through one frozen moment of the fight in the crashing car and credit types instead of names, '
     'such as "Produced by asshats" and "Directed by an overpaid tool". Ryan Reynolds, director Tim Miller and the writers wrote '
     'these credits themselves to set the tone of the film.',
     'Der Vorspann fährt durch einen einzigen eingefrorenen Moment der Schlägerei im verunglückenden Auto und nennt statt Namen '
     'Typen, etwa „Produced by asshats“ und „Directed by an overpaid tool“. Ryan Reynolds, Regisseur Tim Miller und die '
     'Drehbuchautoren haben diese Credits selbst geschrieben, um den Ton des Films vorzugeben.', False),
    (40.0, 146.0, [DE],
     'Deadpool co-creator Rob Liefeld is nodded to in the opening titles: a coffee cup with the name "Rob L." flies through the frozen '
     'scene. Liefeld also makes a cameo as a mercenary in the bar later in the film.',
     'Deadpool-Miterfinder Rob Liefeld wird schon im Vorspann gegrüßt: Ein Kaffeebecher mit dem Namen „Rob L.“ fliegt durch die '
     'eingefrorene Szene. Später hat Liefeld außerdem einen Cameo-Auftritt als Söldner in der Bar.', False),
    (1816.5, 1823.2, [EN + '#Filming', EN + '#Music'],
     'Deadpool was shot under the working title "Wham!". Songs by Wham! and George Michael recur throughout the film, as do references '
     'to the Wham! album "Make It Big".',
     'Gedreht wurde Deadpool unter dem Arbeitstitel „Wham!“. Songs von Wham! und George Michael tauchen im ganzen Film immer wieder '
     'auf, ebenso Anspielungen auf das Wham!-Album „Make It Big“.', False),
    ('cue:bcef4b41-284d-47d1-8408-80b1f5cde2fe', None, [EN + '#Music'],
     'The script set this montage to Frank Sinatra\'s "It Was a Very Good Year". It was changed to Neil Sedaka\'s "Calendar Girl" '
     'during editing.',
     'Im Drehbuch lief unter dieser Montage Frank Sinatras „It Was a Very Good Year“. Erst im Schnitt wurde daraus Neil Sedakas '
     '„Calendar Girl“.', False),
    (2403.0, 2409.3, [EN + '#Post-production'],
     'Deadpool\'s question whether Professor X is played by James McAvoy or Patrick Stewart "at this point in the timeline" was '
     'added after filming. Both actors played the character in the X-Men films, and the line became a favourite with many viewers.',
     'Deadpools Frage, ob Professor X „gerade“ von James McAvoy oder Patrick Stewart gespielt wird, kam erst nach den Dreharbeiten '
     'dazu. Beide Schauspieler verkörperten die Figur in den X-Men-Filmen, und die Zeile wurde für viele Zuschauer zum Lieblingssatz.',
     False),
    (2484.1, 2488.0, [DE, EN + '#Development'],
     'Asking for a suit that is neither green nor animated is a dig at Green Lantern (2011), in which Ryan Reynolds played the title '
     'hero. That film disappointed critics and audiences and set the Deadpool project back.',
     'Die Bitte um einen Anzug, der weder grün noch animiert ist, zielt auf Green Lantern (2011), in dem Ryan Reynolds die Titelrolle '
     'spielte. Der Film enttäuschte Kritik und Publikum und warf das Deadpool-Projekt zurück.', False),
    (2234.8, 2240.0, [EN + '#Writing', DE],
     'Negasonic Teenage Warhead was picked from the list of comic characters available to Fox largely for her name, which comes from '
     'a 1995 song by the band Monster Magnet.',
     'Negasonic Teenage Warhead wurde aus der Liste der für Fox verfügbaren Comicfiguren vor allem wegen ihres Namens ausgewählt. '
     'Der stammt von einem Lied der Band Monster Magnet aus dem Jahr 1995.', False),
    ('cue:45670e1f-097e-4f32-bbd2-86e8dcdb1776', None, [EN + '#Music'],
     'The "Deadpool Rap" by Teamheadkick plays during the montage of Deadpool hunting for Francis.',
     'Der „Deadpool Rap“ von Teamheadkick läuft während der Montage, in der Deadpool Francis jagt.', False),
    (3891.3, 3894.5, [DE],
     'As in the comics, Deadpool keeps breaking the fourth wall and talks directly to the audience.',
     'Wie in den Comics durchbricht Deadpool ständig die vierte Wand und spricht das Publikum direkt an.', False),
    (4700.7, 4704.0, [EN + '#Filming'],
     'Ryan Reynolds improvised this line on set. It was true: there were only two X-Men in the film because of the budget. It became '
     'the favourite line of Jim Gianopulos, then chairman of Fox.',
     'Ryan Reynolds hat diesen Satz am Set improvisiert, und er stimmt: Aus Budgetgründen gibt es im Film nur zwei X-Men. Er wurde '
     'zum Lieblingssatz von Jim Gianopulos, dem damaligen Chef von Fox.', False),
    (4831.3, 4840.5, [EN + '#Writing'],
     'Forty-eight hours before the green light, Fox cut the budget to 58 million dollars. In the rewrite that followed, Deadpool '
     'forgets his bag of guns, which saved the production a costly gunfight in the finale.',
     'Achtundvierzig Stunden vor der Freigabe kürzte Fox das Budget auf 58 Millionen Dollar. Bei der folgenden Überarbeitung des '
     'Drehbuchs vergisst Deadpool seine Waffentasche, was der Produktion eine teure Schießerei im Finale ersparte.', False),
    ('outro-end', 'runtime', [EN + '#Writing', DE],
     'The post-credits scene parodies the one at the end of Ferris Bueller\'s Day Off (1986), whose hero also talks to the audience. '
     'Deadpool, in a bathrobe, tells everyone to go home and announces Cable for the sequel.',
     'Die Szene nach dem Abspann parodiert die am Ende von Ferris macht blau (1986), dessen Held ebenfalls mit dem Publikum spricht. '
     'Deadpool schickt im Bademantel alle nach Hause und kündigt Cable für die Fortsetzung an.', True),
    # About the whole film
    (None, None, [EN + '#Development'],
     'Fox only approved the film after test footage, made in 2012 with a small budget, leaked online in July 2014 to an '
     'enthusiastic response. In September 2025 Ryan Reynolds admitted that he had leaked it himself.',
     'Fox gab den Film erst frei, nachdem 2012 mit kleinem Budget gedrehte Testaufnahmen im Juli 2014 ins Netz gelangten und begeistert '
     'aufgenommen wurden. Im September 2025 gab Ryan Reynolds zu, sie selbst geleakt zu haben.', False),
    (None, None, [EN + '#Post-production', EN + '#Visual_effects'],
     'Colossus is entirely computer-generated. Andre Tricoteux stood in for him on set, T. J. Storm recorded his movements again '
     'later, and his voice was recast in December 2015 with Stefan Kapičić.',
     'Colossus ist vollständig computergeneriert. Am Set stand Andre Tricoteux für ihn, seine Bewegungen nahm später T. J. Storm noch '
     'einmal auf, und seine Stimme wurde im Dezember 2015 mit Stefan Kapičić neu besetzt.', False),
    (None, None, [EN + '#Filming'],
     'The film was shot in and around Vancouver from 23 March to 29 May 2015. The freeway fight was filmed on the Georgia Viaduct, '
     'which the production had for two weeks, rain or shine.',
     'Gedreht wurde vom 23. März bis 29. Mai 2015 in und um Vancouver. Die Kämpfe auf der Schnellstraße entstanden auf dem Georgia '
     'Viaduct, das der Produktion zwei Wochen lang zur Verfügung stand, egal bei welchem Wetter.', False),
    (None, None, [EN + '#Filming'],
     'When Fox would not pay writers Rhett Reese and Paul Wernick to be on set every day, Ryan Reynolds paid their salaries himself.',
     'Als Fox die Drehbuchautoren Rhett Reese und Paul Wernick nicht für jeden Drehtag bezahlen wollte, übernahm Ryan Reynolds ihre '
     'Gage selbst.', False),
    (None, None, [DE],
     'Marvel co-creator Stan Lee has a cameo as the DJ in a strip club.',
     'Marvel-Miterfinder Stan Lee hat einen Cameo-Auftritt als DJ in einem Stripclub.', False),
    (None, None, [EN + '#Visual_effects'],
     'The film has about 1,500 visual effects shots, 700 more than planned, and 800 of them were finished in the last four weeks of '
     'production.',
     'Der Film enthält rund 1.500 Effekteinstellungen, 700 mehr als geplant; 800 davon wurden in den letzten vier Wochen der '
     'Produktion fertig.', False),
]

def build(cues, outro_end, runtime):
    def cue_span(mbid):
        spans = [(c['from'], c['to']) for c in cues if c['mbid'] == mbid]
        return min(s[0] for s in spans), max(s[1] for s in spans)
    out = {'en': [], 'de': []}
    for a, b, sources, en, de, spoiler in items:
        if isinstance(a, str) and a.startswith('cue:'): a, b = cue_span(a[4:])
        elif a == 'outro-end': a, b = outro_end, runtime
        for lang, text in (('en', en), ('de', de)):
            entry = {}
            if a is not None: entry.update({'from': a, 'to': b})
            entry.update({'text': text, 'sources': sources})
            if spoiler: entry['spoiler'] = True
            entry.update({'source': 'language-model', 'confidence': 0.9, 'reviewed': False})
            out[lang].append(entry)
    return out

if __name__ == '__main__':
    import sys
    work = Path(sys.argv[1])
    cues = json.loads((work / 'music' / 'deadpool.json').read_text())
    data = build(cues, 6418.370, 6486.24)
    (work / 'deadpool' / 'trivia.json').write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(len(data['en']), 'items per language')

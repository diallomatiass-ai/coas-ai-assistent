"""
Seed script — opretter demodata til ALLE funktioner.
Kør med: docker compose exec backend python seed.py
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session, engine, Base
from app.models.user import User
from app.models.mail_account import MailAccount
from app.models.email_message import EmailMessage
from app.models.ai_suggestion import AiSuggestion
from app.models.template import Template
from app.models.knowledge_base import KnowledgeBase
from app.models.ai_secretary import AiSecretary
from app.models.secretary_call import SecretaryCall
from app.models.customer import Customer
from app.models.action_item import ActionItem
from app.models.email_reminder import EmailReminder
from app.utils.auth import hash_password


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        now = datetime.now(timezone.utc)

        # ─────────────────────────────────────────────
        # BRUGER
        # ─────────────────────────────────────────────
        user = User(
            id=uuid.uuid4(),
            email="test@mailbot.dk",
            password_hash=hash_password("test1234"),
            name="Martin Jensen",
            company_name="Jensens VVS ApS",
        )
        db.add(user)
        await db.flush()
        print(f"Bruger: {user.email}")

        # ─────────────────────────────────────────────
        # MAILKONTO
        # ─────────────────────────────────────────────
        account = MailAccount(
            id=uuid.uuid4(),
            user_id=user.id,
            email_address="test@mailbot.dk",
            provider="gmail",
            is_active=True,
        )
        db.add(account)
        await db.flush()
        print(f"Mailkonto: {account.email_address}")

        # ─────────────────────────────────────────────
        # KUNDER (10 stk)
        # ─────────────────────────────────────────────
        customers_data = [
            ("Henrik Sørensen", "22 34 56 78", "henrik@soerensenbyg.dk", "Sørensensgade 12", "8000", "Aarhus", "email", "aktiv", ["VVS", "erhverv"], 45000),
            ("Mette Andersen", "31 22 44 55", "mette@privat.dk", "Rosenvej 5", "2100", "København Ø", "call", "aktiv", ["privat"], 8500),
            ("Lars Nielsen VVS", "44 55 66 77", "lars@nielsen-vvs.dk", "Industrivej 88", "5000", "Odense", "manual", "potentiel", ["VVS", "erhverv"], 120000),
            ("Tina Christensen", "55 66 77 88", "tina@gmail.com", "Bakkevej 3", "9000", "Aalborg", "email", "aktiv", ["privat"], 12000),
            ("Bjørn Pedersen", "66 77 88 99", None, "Havnegade 22", "7100", "Vejle", "call", "potentiel", ["erhverv"], 28000),
            ("Sofia Mahmoud", "77 88 99 00", "sofia@sofia-design.dk", "Østergade 9", "1100", "København K", "email", "aktiv", ["privat", "design"], 6500),
            ("Poul Rasmussen Tømrer", "88 99 00 11", "poul@rasmussen-toem.dk", "Skovvej 44", "3400", "Hillerød", "manual", "aktiv", ["tømrer", "erhverv"], 67000),
            ("Anne-Marie Koch", "99 00 11 22", "anne@koch.dk", None, None, None, "email", "inaktiv", ["privat"], 3200),
            ("Jacob Thorsen El", "11 22 33 44", "jacob@thorsen-el.dk", "Elværksvej 1", "6000", "Kolding", "call", "potentiel", ["el", "erhverv"], 85000),
            ("Camilla Brun", "12 34 56 78", "camilla@brun.dk", "Tulipanvej 7", "4600", "Køge", "email", "afsluttet", ["privat"], 9800),
        ]

        customer_objs = []
        for name, phone, email, street, zip_, city, source, status, tags, value in customers_data:
            c = Customer(
                id=uuid.uuid4(),
                user_id=user.id,
                name=name,
                phone=phone,
                email=email,
                address_street=street,
                address_zip=zip_,
                address_city=city,
                source=source,
                status=status,
                tags=tags,
                estimated_value=value,
            )
            db.add(c)
            customer_objs.append(c)
        await db.flush()
        print(f"Kunder: {len(customer_objs)} stk")

        # ─────────────────────────────────────────────
        # EMAILS (14 stk)
        # ─────────────────────────────────────────────
        emails_data = [
            ("henrik@soerensenbyg.dk", "Henrik Sørensen", "Tilbud på badeværelsesrenovering", "Vi ønsker at renovere to badeværelser. Kan I give et tilbud? Vi er fleksible ift. tidspunkt.", "tilbud", "high", 0),
            ("mette@privat.dk", "Mette Andersen", "Vandhane drypper", "Min vandhane i køkkenet drypper konstant. Hvornår kan I komme ud og kigge på det?", "booking", "medium", 1),
            ("lars@nielsen-vvs.dk", "Lars Nielsen VVS", "Samarbejde om større projekt", "Vi er i gang med et større boligprojekt på 24 enheder og søger en underleverandør til VVS.", "tilbud", "high", 2),
            ("tina@gmail.com", "Tina Christensen", "Klage: Varmtvandsbeholder virker ikke", "Den varmtvandsbeholder I installerede for 2 uger siden virker slet ikke. Jeg er meget utilfreds.", "reklamation", "high", 3),
            ("bjorn@pedersen.dk", "Bjørn Pedersen", "Pris på fjernvarmetilslutning", "Hvad koster det at tilslutte vores ejendom til fjernvarmenettet?", "tilbud", "medium", 4),
            ("sofia@sofia-design.dk", "Sofia Mahmoud", "Rørskade i kælder", "Vi har opdaget en rørskade i vores kælder. Der er allerede vand på gulvet. Haster!", "booking", "high", 5),
            ("poul@rasmussen-toem.dk", "Poul Rasmussen", "Faktura #2024-0892", "Vedhæftet faktura for arbejdet udført i november. Betalingsfrist 30 dage.", "faktura", "low", 6),
            ("info@boligstyring.dk", "Boligstyring ApS", "Årskontrakt — vedligeholdelse", "Vi administrerer 180 lejligheder og søger en fast VVS-partner til service og akutopkald.", "tilbud", "high", None),
            ("anne@koch.dk", "Anne-Marie Koch", "Aflysning af tid", "Jeg er desværre nødt til at aflyse den aftalte tid på torsdag. Kan vi rykke til næste uge?", "booking", "low", 7),
            ("jacob@thorsen-el.dk", "Jacob Thorsen El", "Fælles tilbud — kombiprojekt", "Jeg har en kunde der ønsker nyt badeværelse. Lad os give et samlet tilbud — el + VVS.", "tilbud", "medium", 8),
            ("camilla@brun.dk", "Camilla Brun", "Tak for god service!", "Vil bare sige tak for det hurtige og professionelle arbejde. Vi er meget tilfredse.", "andet", "low", 9),
            ("spam@reklame.com", "Tilbud til dig!", "Vind en iPhone 15 — klik nu!", "Du er udvalgt til at vinde en iPhone. Klik her inden for 24 timer!!!", "spam", "low", None),
            ("leverandor@broen.dk", "Broen VVS Engros", "Prisliste 2026 + nye produkter", "Vedhæftet vores opdaterede prisliste for 2026. Kontakt os for mængderabat.", "leverandor", "low", None),
            ("intern@jensens-vvs.dk", "Kontor", "Ny ferieplan Q2 2026", "Hermed ferieplan for Q2. Husk at registrere ønsker inden 1. marts.", "intern", "low", None),
        ]

        email_objs = []
        for i, (from_addr, from_name, subject, body, category, urgency, cust_idx) in enumerate(emails_data):
            email = EmailMessage(
                id=uuid.uuid4(),
                account_id=account.id,
                provider_id=f"msg_{i+1:04d}",
                from_address=from_addr,
                from_name=from_name,
                to_address="test@mailbot.dk",
                subject=subject,
                body_text=body,
                received_at=now - timedelta(hours=i * 4 + 1),
                category=category,
                urgency=urgency,
                processed=True,
                is_read=i > 6,
                customer_id=customer_objs[cust_idx].id if cust_idx is not None else None,
            )
            db.add(email)
            email_objs.append(email)
        await db.flush()
        print(f"Emails: {len(email_objs)} stk")

        # ─────────────────────────────────────────────
        # AI-FORSLAG (6 stk)
        # ─────────────────────────────────────────────
        suggestions_data = [
            (0, "Kære Henrik,\n\nTak for din henvendelse. Vi ser frem til at renovere jeres badeværelser.\n\nVi foreslår et besøg til syn og opmåling, hvorefter vi sender et detaljeret tilbud inden for 3 hverdage.\n\nPasser tirsdag den 4. marts kl. 10:00?\n\nMed venlig hilsen\nMartin Jensen\nJensens VVS ApS · 44 55 66 77"),
            (1, "Kære Mette,\n\nTak for din henvendelse. En dryppende vandhane er irriterende — vi fikser det hurtigt.\n\nVi har en ledig tid allerede i morgen, onsdag, kl. 13:00-15:00. Passer det?\n\nMed venlig hilsen\nMartin Jensen\nJensens VVS ApS"),
            (3, "Kære Tina,\n\nVi beklager dybt, at din nye varmtvandsbeholder ikke fungerer korrekt.\n\nVi sender en tekniker ud i dag inden kl. 17:00 for at undersøge og udbedre fejlen — uden beregning.\n\nMed venlig hilsen\nMartin Jensen\nJensens VVS ApS"),
            (5, "Kære Sofia,\n\nVi forstår at det haster med rørskaden. Vi sender en nødteknikker inden for 2 timer.\n\nRing venligst på 44 55 66 77 for direkte koordinering.\n\nMed venlig hilsen\nMartin Jensen\nJensens VVS ApS"),
            (7, "Kære Boligstyring ApS,\n\nTak for jeres henvendelse. Et samarbejde om 180 lejligheder lyder meget interessant.\n\nJeg foreslår et møde, hvor vi kan gennemgå jeres behov. Hvornår passer det jer?\n\nMed venlig hilsen\nMartin Jensen\nJensens VVS ApS"),
            (9, "Kære Jacob,\n\nEt kombineret tilbud på el og VVS er en god løsning for kunden.\n\nJeg er ledig torsdag eller fredag denne uge. Hvad passer dig?\n\nMed venlig hilsen\nMartin Jensen\nJensens VVS ApS"),
        ]
        for email_idx, text in suggestions_data:
            db.add(AiSuggestion(
                id=uuid.uuid4(),
                email_id=email_objs[email_idx].id,
                suggested_text=text,
                status="pending",
            ))
        print(f"AI-forslag: {len(suggestions_data)} stk")

        # ─────────────────────────────────────────────
        # SKABELONER (5 stk)
        # ─────────────────────────────────────────────
        templates = [
            Template(id=uuid.uuid4(), user_id=user.id, name="Tilbudsbekræftelse", body="Kære {{navn}},\n\nTak for din forespørgsel. Vi sender et detaljeret tilbud inden for 2 hverdage.\n\nMed venlig hilsen\nJensens VVS ApS\nTlf. 44 55 66 77", category="tilbud"),
            Template(id=uuid.uuid4(), user_id=user.id, name="Tidsbestilling", body="Kære {{navn}},\n\nVi bekræfter din tid {{dato}} kl. {{tidspunkt}}.\n\nVores teknikere ringer 30 min. i forvejen.\n\nMed venlig hilsen\nJensens VVS ApS", category="booking"),
            Template(id=uuid.uuid4(), user_id=user.id, name="Reklamationssvar", body="Kære {{navn}},\n\nVi beklager de problemer du oplever og tager det meget alvorligt.\n\nVi sender en tekniker ud {{dato}} — arbejdet sker uden beregning under garantien.\n\nMed venlig hilsen\nJensens VVS ApS", category="reklamation"),
            Template(id=uuid.uuid4(), user_id=user.id, name="Fakturaopfølgning", body="Kære {{navn}},\n\nVenlig påmindelse om faktura #{{fakturanr}} på kr. {{beløb}} med forfaldsdato {{dato}}.\n\nBetaling via MobilePay 12345 eller bankoverførsel.\n\nMed venlig hilsen\nJensens VVS ApS", category="faktura"),
            Template(id=uuid.uuid4(), user_id=user.id, name="Aflysningsbekræftelse", body="Kære {{navn}},\n\nVi bekræfter aflysning af din tid {{dato}}. Vi håber at høre fra dig snart.\n\nMed venlig hilsen\nJensens VVS ApS", category="booking"),
        ]
        for t in templates:
            db.add(t)
        print(f"Skabeloner: {len(templates)} stk")

        # ─────────────────────────────────────────────
        # VIDENBASE (6 poster)
        # ─────────────────────────────────────────────
        kb_entries = [
            KnowledgeBase(id=uuid.uuid4(), user_id=user.id, title="Leveringstider", content="Akutopkald: inden for 2 timer. Standardopgave: 1-3 hverdage. Større renoveringer: aftales individuelt.", entry_type="faq"),
            KnowledgeBase(id=uuid.uuid4(), user_id=user.id, title="Priser", content="Timepris hverdage: 695 kr. ex. moms. Tillæg weekend/aften: 50%. Akut tillæg: 100%. Opstartsgebyr: 395 kr.", entry_type="faq"),
            KnowledgeBase(id=uuid.uuid4(), user_id=user.id, title="Garantivilkår", content="Garanti på udført arbejde: 5 år. Garanti på nye installationer: 2 år. Reklamationer behandles inden for 24 timer.", entry_type="faq"),
            KnowledgeBase(id=uuid.uuid4(), user_id=user.id, title="Åbningstider", content="Mandag-fredag: 07:00-16:00. Vagttelefon (akut): Alle dage 06:00-22:00.", entry_type="hours"),
            KnowledgeBase(id=uuid.uuid4(), user_id=user.id, title="Tone of voice", content="Brug altid en professionel og imødekommende tone. Start med 'Kære [fornavn]'. Slut med 'Med venlig hilsen\nMartin Jensen\nJensens VVS ApS'.", entry_type="tone"),
            KnowledgeBase(id=uuid.uuid4(), user_id=user.id, title="Serviceområde", content="Aarhus og omegn inden for 40 km: Randers, Silkeborg, Skanderborg, Horsens, Odder, Ebeltoft.", entry_type="faq"),
        ]
        for kb in kb_entries:
            db.add(kb)
        print(f"Videnbase: {len(kb_entries)} poster")

        # ─────────────────────────────────────────────
        # AI SEKRETÆR
        # ─────────────────────────────────────────────
        secretary = AiSecretary(
            id=uuid.uuid4(),
            user_id=user.id,
            business_name="Jensens VVS ApS",
            industry="vvs",
            phone_number="+45 44 55 66 77",
            cvr_number="12345678",
            contact_persons=[
                {"name": "Martin Jensen", "phone": "44 55 66 77", "email": "martin@jensens-vvs.dk"},
                {"name": "Peder Larsen (tekniker)", "phone": "55 44 33 22", "email": None},
            ],
            business_address="Håndværkervej 12, 8000 Aarhus C",
            business_email="test@mailbot.dk",
            greeting_text="Goddag, du har ringet til Jensens VVS ApS. Jeg er jeres digitale assistent og kan hjælpe dig med at registrere din henvendelse. Er det en akut skade, en tidsbestilling eller noget andet?",
            system_prompt="Du er AI-telefonsekretær for Jensens VVS ApS i Aarhus. Registrér kundehenvendelser, book tider og vurdér haster. Spørg altid efter: navn, telefonnummer, adresse og beskrivelse af problemet.",
            required_fields=["name", "phone", "address", "description"],
            knowledge_items=[
                {"question": "Hvad koster en akutopkald?", "answer": "Ca. 1.390 kr./time ex. moms (695 kr. + 100% tillæg)."},
                {"question": "Hvornår kan I komme?", "answer": "Akut: inden for 2 timer. Normal tid: 1-3 hverdage."},
                {"question": "Hvad er jeres serviceområde?", "answer": "Aarhus og omegn inden for 40 km."},
            ],
            ivr_options=[
                {"key": "1", "label": "Akut skade", "action": "urgent"},
                {"key": "2", "label": "Book tid", "action": "booking"},
                {"key": "3", "label": "Spørgsmål om pris", "action": "inquiry"},
                {"key": "0", "label": "Tal med medarbejder", "action": "transfer"},
            ],
            is_active=True,
            confirmation_enabled=True,
            confirmation_template="Kære {caller_name},\n\nTak for din henvendelse til {business_name}.\n\nVi har registreret: {summary}\n\nVi vender tilbage inden for {response_deadline}.\n\nMed venlig hilsen\nJensens VVS ApS",
            response_deadline_hours=4,
        )
        db.add(secretary)
        await db.flush()
        print(f"AI Sekretær: {secretary.business_name}")

        # ─────────────────────────────────────────────
        # OPKALD (10 stk)
        # ─────────────────────────────────────────────
        calls_data = [
            ("Henrik Sørensen", "22 34 56 78", "Sørensensgade 12, Aarhus", "Kunden ønsker tilbud på badeværelsesrenovering — 2 badeværelser, ønsker besøg til opmåling.", "medium", "new", 1, 0),
            ("Ukendt", "71 23 45 67", None, "Akut vandbrud i kælder — vand strømmer ind. Kunden er meget stresset.", "high", "new", 2, None),
            ("Mette Andersen", "31 22 44 55", "Rosenvej 5, København Ø", "Dryppende vandhane i køkken, ønsker tid hurtigst muligt.", "low", "new", 3, 1),
            ("Lars Nielsen VVS", "44 55 66 77", "Industrivej 88, Odense", "Stor entreprise — 24 boliger under opførelse, søger fast VVS-underleverandør.", "high", "contacted", 5, 2),
            ("Bjørn Pedersen", "66 77 88 99", "Havnegade 22, Vejle", "Pris på fjernvarmetilslutning til erhvervsejendom, 800 m².", "medium", "contacted", 8, 4),
            ("Sofia Mahmoud", "77 88 99 00", "Østergade 9, København K", "Rørskade i kælder med vand på gulvet. Teknikker sendt afsted.", "high", "contacted", 10, 5),
            ("Anonym", "20 33 44 55", None, "Spørger om priser på varmepumpe-installation til parcelhus.", "low", "contacted", 14, None),
            ("Poul Rasmussen", "88 99 00 11", "Skovvej 44, Hillerød", "Status på faktura #2024-0892. Bekræftet modtaget og betales næste uge.", "low", "resolved", 24, 6),
            ("Camilla Brun", "12 34 56 78", "Tulipanvej 7, Køge", "Positiv feedback på seneste arbejde. Vil anbefale til naboer.", "low", "resolved", 36, 9),
            ("Jacob Thorsen El", "11 22 33 44", "Elværksvej 1, Kolding", "Kombiprojekt drøftet — aftalt møde fredag kl. 10:00 hos kunden.", "medium", "resolved", 48, 8),
        ]

        call_objs = []
        for caller, phone, address, summary, urgency, status, hours_ago, cust_idx in calls_data:
            call = SecretaryCall(
                id=uuid.uuid4(),
                secretary_id=secretary.id,
                customer_id=customer_objs[cust_idx].id if cust_idx is not None else None,
                caller_name=caller,
                caller_phone=phone,
                caller_address=address,
                summary=summary,
                urgency=urgency,
                status=status,
                called_at=now - timedelta(hours=hours_ago),
                confirmation_sent_at=now - timedelta(hours=hours_ago - 0.1) if status != "new" else None,
            )
            db.add(call)
            call_objs.append(call)
        await db.flush()
        print(f"Opkald: {len(call_objs)} stk")

        # ─────────────────────────────────────────────
        # OPGAVER / ACTION ITEMS (8 stk)
        # ─────────────────────────────────────────────
        action_items_data = [
            (customer_objs[0], call_objs[0], "send_tilbud", "Send tilbud på badeværelsesrenovering × 2 — opmåling aftalt tirsdag.", "pending", now + timedelta(days=2)),
            (customer_objs[1], call_objs[2], "ring_tilbage", "Ring tilbage og bekræft tid til dryppende vandhane.", "pending", now + timedelta(hours=4)),
            (customer_objs[2], call_objs[3], "følg_op", "Følg op på stort entrepriseprojekt — 24 boliger. Forbered referencer.", "pending", now + timedelta(days=5)),
            (customer_objs[4], call_objs[4], "send_tilbud", "Udarbejd tilbud på fjernvarmetilslutning — 800 m² erhvervsejendom.", "pending", now + timedelta(days=3)),
            (customer_objs[5], call_objs[5], "ring_tilbage", "Tjek op med Sofia — er rørskaden udbedret tilfredsstillende?", "overdue", now - timedelta(hours=2)),
            (customer_objs[6], call_objs[7], "send_faktura", "Fakturaopfølgning #2024-0892 — betales næste uge.", "done", now - timedelta(days=1)),
            (customer_objs[8], call_objs[9], "book_møde", "Møde med Jacob Thorsen El fredag kl. 10:00 — husk tegninger.", "done", now + timedelta(days=1)),
            (None, None, "intern", "Opdater prislisten for 2026 på hjemmesiden inden udgangen af måneden.", "pending", now + timedelta(days=10)),
        ]
        for cust, call, action, desc, status, deadline in action_items_data:
            db.add(ActionItem(
                id=uuid.uuid4(),
                user_id=user.id,
                customer_id=cust.id if cust else None,
                call_id=call.id if call else None,
                action=action,
                description=desc,
                status=status,
                deadline=deadline,
            ))
        print(f"Opgaver: {len(action_items_data)} stk")

        # ─────────────────────────────────────────────
        # EMAIL PÅMINDELSER (3 stk)
        # ─────────────────────────────────────────────
        reminders_data = [
            (email_objs[0], "follow_up", "Følg op på tilbudsforespørgsel fra Henrik Sørensen"),
            (email_objs[4], "unanswered", "Send prisoverslag på fjernvarme til Bjørn Pedersen"),
            (email_objs[7], "follow_up", "Book møde med Boligstyring ApS om årskontrakt"),
        ]
        for email_obj, r_type, message in reminders_data:
            db.add(EmailReminder(
                id=uuid.uuid4(),
                user_id=user.id,
                email_id=email_obj.id,
                reminder_type=r_type,
                message=message,
                is_dismissed=False,
            ))
        print(f"Påmindelser: {len(reminders_data)} stk")

        await db.commit()
        print("\nSeed fuldfoert! Alt klar til demonstration.")
        print("Login: test@mailbot.dk / test1234")
        print("Aabn: http://localhost")


if __name__ == "__main__":
    asyncio.run(seed())

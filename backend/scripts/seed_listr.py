"""Seeds listr's product catalog with ~220 common Dutch supermarket groceries across 12
categories. Idempotent (get-or-create by name), safe to re-run -- running it again after the
user has added their own products via the Producten page just leaves those untouched and
skips any catalog item that already exists.

Usage (from backend/):
    python -m scripts.seed_listr
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.repositories import listr_category_repo, listr_item_repo  # noqa: E402

# category name -> [(item name, default unit), ...]
CATALOG: dict[str, list[tuple[str, str]]] = {
    "Groente & Fruit": [
        ("Aardappelen", "kg"), ("Uien", "kg"), ("Wortelen", "zak"), ("Tomaten", "kg"),
        ("Komkommer", "stuks"), ("Paprika", "stuks"), ("Sla", "krop"), ("Spinazie", "zak"),
        ("Broccoli", "stuks"), ("Bloemkool", "stuks"), ("Courgette", "stuks"),
        ("Champignons", "bakje"), ("Knoflook", "bol"), ("Prei", "stuks"),
        ("Sperziebonen", "zak"), ("Appels", "kg"), ("Bananen", "kg"),
        ("Sinaasappels", "net"), ("Peren", "kg"), ("Druiven", "bakje"), ("Citroen", "stuks"),
        ("Avocado", "stuks"), ("Aardbeien", "bakje"), ("Mandarijnen", "net"), ("Kiwi's", "stuks"),
    ],
    "Zuivel & Eieren": [
        ("Halfvolle melk", "liter"), ("Volle melk", "liter"), ("Magere melk", "liter"),
        ("Karnemelk", "liter"), ("Yoghurt", "pak"), ("Griekse yoghurt", "pot"),
        ("Kwark", "pak"), ("Slagroom", "pak"), ("Boter", "pak"), ("Margarine", "kuipje"),
        ("Roomboter", "pak"), ("Eieren", "doos"), ("Jong belegen kaas", "gram"),
        ("Oude kaas", "gram"), ("Geraspte kaas", "zak"), ("Mozzarella", "bol"),
        ("Feta", "blokje"), ("Crème fraîche", "bakje"), ("Vla", "pak"), ("Chocolademelk", "pak"),
    ],
    "Vlees & Vis": [
        ("Kipfilet", "gram"), ("Kipdijfilet", "gram"), ("Half-om-half gehakt", "gram"),
        ("Rundergehakt", "gram"), ("Speklapjes", "gram"), ("Bacon", "pak"),
        ("Rookworst", "stuks"), ("Hamburgers", "pak"), ("Kalkoenfilet", "gram"),
        ("Schnitzel", "stuks"), ("Runderlappen", "gram"), ("Zalm", "gram"),
        ("Kabeljauwfilet", "gram"), ("Tonijn", "blik"), ("Garnalen", "zak"),
        ("Vissticks", "doos"), ("Ham", "plakken"), ("Salami", "plakken"),
        ("Kipnuggets", "zak"), ("Spekjes", "bakje"),
    ],
    "Brood & Bakkerij": [
        ("Wit brood", "stuks"), ("Bruin brood", "stuks"), ("Volkoren brood", "stuks"),
        ("Stokbrood", "stuks"), ("Croissants", "zak"), ("Beschuit", "rol"),
        ("Krentenbollen", "zak"), ("Wraps", "pak"), ("Pitabroodjes", "zak"),
        ("Bagels", "zak"), ("Toastbrood", "pak"), ("Knäckebröd", "pak"),
        ("Ontbijtkoek", "pak"), ("Krentenbrood", "stuks"), ("Donuts", "doos"),
    ],
    "Pasta, Rijst & Wereldkeuken": [
        ("Spaghetti", "pak"), ("Penne", "pak"), ("Macaroni", "pak"), ("Basmatirijst", "pak"),
        ("Zilvervliesrijst", "pak"), ("Noedels", "pak"), ("Couscous", "pak"), ("Bulgur", "pak"),
        ("Lasagnebladen", "pak"), ("Tortilla wraps", "pak"), ("Taco schelpen", "doos"),
        ("Nasi kruiden", "zakje"), ("Currypasta", "potje"), ("Kokosmelk", "blik"),
        ("Sojasaus", "fles"), ("Ketjap", "fles"), ("Sushirijst", "pak"), ("Ravioli", "pak"),
    ],
    "Conserven, Soepen & Sauzen": [
        ("Tomatenblokjes", "blik"), ("Kidneybonen", "blik"), ("Kikkererwten", "blik"),
        ("Maïs", "blik"), ("Erwtensoep", "pak"), ("Tomatensoep", "pak"),
        ("Groentebouillon", "pot"), ("Kippenbouillon", "pot"), ("Pastasaus", "pot"),
        ("Pesto", "potje"), ("Mayonaise", "fles"), ("Ketchup", "fles"), ("Mosterd", "fles"),
        ("Barbecuesaus", "fles"), ("Satésaus", "pot"), ("Appelmoes", "pot"),
        ("Zilveruitjes", "potje"), ("Augurken", "pot"),
    ],
    "Ontbijt & Beleg": [
        ("Cornflakes", "doos"), ("Havermout", "pak"), ("Muesli", "pak"), ("Pindakaas", "pot"),
        ("Jam", "pot"), ("Hagelslag", "pak"), ("Chocopasta", "pot"), ("Honing", "pot"),
        ("Stroop", "fles"), ("Vruchtenhagel", "pak"), ("Kaaspasta", "kuipje"),
        ("Crackers", "pak"), ("Beschuit met muisjes", "rol"), ("Nutella", "pot"),
        ("Cruesli", "pak"),
    ],
    "Snacks & Snoep": [
        ("Chips", "zak"), ("Zoutjes", "zak"), ("Nootjes", "zak"), ("Popcorn", "zak"),
        ("Chocoladereep", "stuks"), ("Drop", "zak"), ("Stroopwafels", "pak"),
        ("Bastognekoeken", "pak"), ("Wafels", "pak"), ("Rijstwafels", "pak"),
        ("Studentenhaver", "zak"), ("Winegums", "zak"), ("M&M's", "zak"),
        ("Cracottes", "pak"), ("Toastjes", "pak"), ("Bitterballen", "doos"),
        ("Kaasblokjes", "bakje"), ("Worstenbroodjes", "doos"),
    ],
    "Dranken": [
        ("Cola", "fles"), ("Sinas", "fles"), ("Cassis", "fles"), ("Ranja", "fles"),
        ("Appelsap", "pak"), ("Sinaasappelsap", "pak"), ("Mineraalwater", "fles"),
        ("Spa rood", "fles"), ("Spa blauw", "fles"), ("Bier", "krat"), ("Rode wijn", "fles"),
        ("Witte wijn", "fles"), ("Koffiebonen", "pak"), ("Koffiepads", "pak"), ("Thee", "doos"),
        ("IJsthee", "fles"), ("Energiedrank", "blik"), ("Limonadesiroop", "fles"),
        ("Tonic", "fles"), ("Sportdrank", "fles"),
    ],
    "Diepvries": [
        ("Diepvries doperwten", "zak"), ("Diepvries spinazie", "zak"),
        ("Diepvriespizza", "stuks"), ("Frites", "zak"), ("Kroketten", "doos"),
        ("Diepvries vis", "zak"), ("Vanille-ijs", "bak"), ("Aardbeien-ijs", "bak"),
        ("Loempia's", "doos"), ("Diepvriesfruit", "zak"), ("Bladerdeeg", "pak"),
        ("Diepvries kipstukjes", "zak"), ("Diepvries bitterballen", "doos"),
        ("Afbakbroodjes", "zak"), ("Roomijs bakje", "bak"),
    ],
    "Kruiden, Sauzen & Olie": [
        ("Zout", "pak"), ("Peper", "potje"), ("Paprikapoeder", "potje"), ("Oregano", "potje"),
        ("Gedroogde basilicum", "potje"), ("Italiaanse kruiden", "potje"),
        ("Kerriepoeder", "potje"), ("Knoflookpoeder", "potje"), ("Bouillonblokjes", "doos"),
        ("Olijfolie", "fles"), ("Zonnebloemolie", "fles"), ("Frituurolie", "fles"),
        ("Balsamicoazijn", "fles"), ("Sla-olie", "fles"), ("Vanillesuiker", "zakje"),
        ("Bakpoeder", "zakje"), ("Bloem", "pak"), ("Suiker", "pak"),
    ],
    "Huishouden & Verzorging": [
        ("Wc-papier", "pak"), ("Keukenpapier", "rol"), ("Afwasmiddel", "fles"),
        ("Wasmiddel", "fles"), ("Wasverzachter", "fles"), ("Vaatwastabletten", "pak"),
        ("Allesreiniger", "fles"), ("Vuilniszakken", "rol"), ("Aluminiumfolie", "rol"),
        ("Huishoudfolie", "rol"), ("Tandpasta", "tube"), ("Shampoo", "fles"),
        ("Douchegel", "fles"), ("Deodorant", "stuks"), ("Zeep", "stuks"), ("Tissues", "doos"),
        ("Luiers", "pak"), ("Scheermesjes", "pak"), ("Wattenstaafjes", "pak"),
        ("Afwasborstel", "stuks"),
    ],
}


def main() -> None:
    db = SessionLocal()
    try:
        created_categories = 0
        created_items = 0
        for position, (category_name, items) in enumerate(CATALOG.items()):
            category = listr_category_repo.get_by_name(db, category_name)
            if category is None:
                category = listr_category_repo.create_category(db, name=category_name, sort_order=position)
                created_categories += 1
            for item_name, unit in items:
                existing = listr_item_repo.get_by_name(db, item_name)
                if existing is None:
                    listr_item_repo.create_item(
                        db, name=item_name, category_id=category.id, default_unit=unit
                    )
                    created_items += 1
        db.commit()
        total_items = sum(len(items) for items in CATALOG.values())
        print(
            f"Seed complete: {created_categories} new categories, {created_items} new items "
            f"(catalog defines {len(CATALOG)} categories, {total_items} items -- others already existed)."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()

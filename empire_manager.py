# empire_manager.py
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
import re
import json
from datetime import datetime

class ToolTip:
    """Affiche une info-bulle au survol"""
    def __init__(self, widget, texte):
        self.widget = widget
        self.texte = texte
        self.tip_window = None
        widget.bind('<Enter>', self.enter)
        widget.bind('<Leave>', self.leave)
    
    def enter(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tip_window, text=self.texte, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("Segoe UI", 9))
        label.pack()
    
    def leave(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

# ==================== DONNÉES RACES ====================
RACES = {
    "Abysséens": {
        "criteria": {
            "eau": {"min": 80, "max": 100, "weight": 30},
            "vent_solaire": {"min": 0, "max": 20, "weight": 25},
            "gravite": {"min": 1.5, "max": 2.5, "weight": 20}
        }
    },
    "Aérions": {
        "criteria": {
            "gravite": {"min": 0.3, "max": 0.7, "weight": 30},
            "atmosphere": {"min": 90, "max": 100, "weight": 30},
            "eau": {"min": 0, "max": 20, "weight": 20}
        }
    },
    "Lithars": {
        "criteria": {
            "temperature": {"min": 100, "max": 300, "weight": 30},
            "eau": {"min": 0, "max": 30, "weight": 25},
            "gravite": {"min": 2, "max": 3, "weight": 20},
            "vent_solaire": {"min": 60, "max": 100, "weight": 20}
        }
    },
    "Mécalythes": {
        "criteria": {
            "magnetisme": {"min": 80, "max": 100, "weight": 30},
            "eau": {"min": 10, "max": 40, "weight": 20},
            "vent_solaire": {"min": 20, "max": 50, "weight": 20}
        }
    },
    "Némoryx": {
        "criteria": {
            "temperature": {"min": 15, "max": 35, "weight": 25},
            "atmosphere": {"min": 70, "max": 90, "weight": 25},
            "eau": {"min": 40, "max": 70, "weight": 20},
            "vent_solaire": {"min": 10, "max": 30, "weight": 20}
        }
    },
    "Sylvaë": {
        "criteria": {
            "vent_solaire": {"min": 0, "max": 20, "weight": 30},
            "eau": {"min": 50, "max": 80, "weight": 25},
            "atmosphere": {"min": 80, "max": 100, "weight": 25}
        }
    },
    "Terrans": {
        "criteria": {
            "gravite": {"min": 0.8, "max": 1.2, "weight": 20},
            "atmosphere": {"min": 60, "max": 90, "weight": 20},
            "temperature": {"min": -10, "max": 40, "weight": 15},
            "vent_solaire": {"min": 10, "max": 40, "weight": 15},
            "eau": {"min": 30, "max": 70, "weight": 15}
        }
    },
    "Xyrrh": {
        "criteria": {
            "eau": {"min": 0, "max": 20, "weight": 25},
            "temperature": {"min": 50, "max": 200, "weight": 25},
            "vent_solaire": {"min": 50, "max": 80, "weight": 20},
            "atmosphere": {"min": 10, "max": 40, "weight": 20}
        }
    }
}

# Couleurs des pastilles
COLORS = {
    "excellent": "#2ecc71",  # Vert
    "bon": "#f39c12",        # Orange/Jaune
    "mauvais": "#e74c3c",    # Rouge
    "neutre": "#95a5a6"      # Gris
}

def get_race_color(valeur, min_val, max_val):
    """Retourne la couleur selon la position par rapport à la plage idéale"""
    if min_val <= valeur <= max_val:
        return COLORS["excellent"]
    # Marge de 20% autour de la plage
    marge_min = min_val - (max_val - min_val) * 0.2
    marge_max = max_val + (max_val - min_val) * 0.2
    if marge_min <= valeur <= marge_max:
        return COLORS["bon"]
    return COLORS["mauvais"]

def get_ressource_color(pourcentage):
    """Retourne la couleur selon le pourcentage de la ressource"""
    if pourcentage >= 80:
        return COLORS["excellent"]
    elif pourcentage >= 50:
        return COLORS["bon"]
    return COLORS["mauvais"]

# ==================== PARSING ====================
def parser_rapport_sonde(texte):
    lignes = [l.strip() for l in texte.strip().split('\n') if l.strip()]
    
    resultat = {
        "nom_planete": "",
        "systeme": "",
        "position": "",
        "ressources": []
    }
    # 0 trouver le nom de la planète
    for idx, ligne in enumerate(lignes):
        if ligne.lower() == "emplacement" and idx > 0:
            resultat["nom_planete"] = lignes[idx - 1]
            break

    # ⭐ 1. Trouver la BONNE coordonnée (celle près des caractéristiques)
    coordonnees = []
    for idx, ligne in enumerate(lignes):
        parties = ligne.split()
        if len(parties) >= 2:
            premier = parties[0].replace("-", "")
            if premier.isdigit() and ":" in parties[1]:
                # Vérifie si les lignes suivantes contiennent des caractéristiques
                for offset in range(1, 5):
                    if idx + offset < len(lignes):
                        ligne_suivante = lignes[idx + offset]
                        if any(key in ligne_suivante for key in ["Eau", "Gravité", "Température", "Magnétisme", "Vent Solaire", "Atmosphère"]):
                            coordonnees.append((idx, parties[0], parties[1]))
                            break
    
    # Prend la dernière coordonnée trouvée (celle juste avant les caractéristiques)
    if coordonnees:
        _, systeme, position = coordonnees[-1]
        resultat["systeme"] = systeme
        resultat["position"] = position
    else:
        # Fallback : cherche une coordonnée simple
        for ligne in lignes:
            parties = ligne.split()
            if len(parties) >= 2:
                premier = parties[0].replace("-", "")
                if premier.isdigit() and ":" in parties[1]:
                    resultat["systeme"] = parties[0]
                    resultat["position"] = parties[1]
                    break
    
    # ⭐ 2. Parcourir toutes les lignes pour trouver les valeurs
    for i, ligne in enumerate(lignes):
        import re
        
        # EauXX%
        if "Eau" in ligne and "%" in ligne:
            match = re.search(r"Eau([\d.]+%)", ligne)
            if match:
                resultat["eau"] = match.group(1)
        
        # GravitéxX.XX
        elif "Gravitéx" in ligne:
            match = re.search(r"Gravitéx([\d.]+)", ligne)
            if match:
                resultat["gravite"] = match.group(1)
        
        # TempératureXXX°C
        elif "Température" in ligne and "°C" in ligne:
            match = re.search(r"Température(-?[\d.]+°C)", ligne)
            if match:
                resultat["temperature"] = match.group(1)
        
        # MagnétismeXX
        elif "Magnétisme" in ligne:
            match = re.search(r"Magnétisme(\d+)", ligne)
            if match:
                resultat["magnetisme"] = match.group(1)
        
        # Vent SolaireXX
        elif "Vent Solaire" in ligne:
            match = re.search(r"Vent Solaire(\d+)", ligne)
            if match:
                resultat["vent_solaire"] = match.group(1)
        
        # AtmosphèreXX%
        elif "Atmosphère" in ligne and "%" in ligne:
            match = re.search(r"Atmosphère([\d.]+%)", ligne)
            if match:
                resultat["atmosphere"] = match.group(1)
        
        # ⭐ 3. Ressources : cherche "TitaneTitane" etc.
        ressources_connues = ["Titane", "Cuivre", "Aluminium", "Silicium", 
                              "Fer", "Mercure", "Uranium", "Krypton", 
                              "Azote", "Hydrogène"]
        
        for res in ressources_connues:
            if ligne == res + res:
                # La ressource est trouvée, cherche le pourcentage dans les 3 lignes suivantes
                for j in range(i+1, min(i+5, len(lignes))):
                    if "%" in lignes[j]:
                        match_pct = re.search(r"([\d.]+%)", lignes[j])
                        if match_pct:
                            resultat["ressources"].append({
                                "nom": res,
                                "pourcentage": match_pct.group(1),
                                "efficacite": lignes[j+1] if j+1 < len(lignes) else ""
                            })
                        break
                break
    
    # Valeurs par défaut
    defaults = ["eau", "gravite", "temperature", "magnetisme", "vent_solaire", "atmosphere"]
    for key in defaults:
        if key not in resultat or not resultat[key]:
            resultat[key] = "0"
    
    return resultat
# ==================== BASE DE DONNÉES ====================
DB_FILE = "planetes.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS planetes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            systeme TEXT,
            position TEXT,
            eau REAL,
            gravite REAL,
            temperature REAL,
            magnetisme REAL,
            vent_solaire REAL,
            atmosphere REAL,
            date_ajout TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Ajouter la colonne notes si elle n'existe pas (pour les anciennes bases)
    try:
        cursor.execute("ALTER TABLE planetes ADD COLUMN notes TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE planetes ADD COLUMN nom_planete TEXT")
    except sqlite3.OperationalError:
        pass  # La colonne existe déjà

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ressources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            planete_id INTEGER,
            nom TEXT,
            pourcentage REAL,
            efficacite TEXT,
            FOREIGN KEY (planete_id) REFERENCES planetes(id)
        )
    ''')
    conn.commit()
    conn.close()

def ajouter_planete(donnees):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO planetes (nom_planete, systeme, position, eau, gravite, temperature, 
                              magnetisme, vent_solaire, atmosphere)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        donnees.get('nom_planete', ''),
        donnees['systeme'],
        donnees['position'],
        float(donnees.get('eau', '0%').rstrip('%')),
        float(donnees.get('gravite', 0)),
        float(donnees.get('temperature', '0°C').rstrip('°C')),
        float(donnees.get('magnetisme', 0)),
        float(donnees.get('vent_solaire', 0)),
        float(donnees.get('atmosphere', '0%').rstrip('%'))
    ))
    
    planete_id = cursor.lastrowid
    
    for res in donnees['ressources']:
        cursor.execute('''
            INSERT INTO ressources (planete_id, nom, pourcentage, efficacite)
            VALUES (?, ?, ?, ?)
        ''', (planete_id, res['nom'], float(res['pourcentage'].rstrip('%')), res['efficacite']))
    
    conn.commit()
    conn.close()
    return planete_id

def rechercher_planetes(criteres_ressources):
    """Recherche les planètes qui ont TOUTES les ressources demandées"""
    if not criteres_ressources:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT id, nom_planete, systeme, position, eau, gravite, temperature, magnetisme, vent_solaire, atmosphere FROM planetes ORDER BY date_ajout DESC")
        resultats = cursor.fetchall()
        conn.close()
        planetes = []
        for r in resultats:
            planetes.append({
                "id": r[0],
                "nom_planete": r[1],
                "systeme": r[2],
                "position": r[3],
                "eau": r[4],
                "gravite": r[5],
                "temperature": r[6],
                "magnetisme": r[7],
                "vent_solaire": r[8],
                "atmosphere": r[9]
            })
        return planetes
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    conditions = []
    params = []
    for i, crit in enumerate(criteres_ressources):
        conditions.append(f"""
            EXISTS (
                SELECT 1 FROM ressources r{i}
                WHERE r{i}.planete_id = p.id
                AND r{i}.nom = ?
                AND r{i}.pourcentage >= ?
            )
        """)
        params.extend([crit["nom"], crit["min_pourcentage"]])
    
    requete = f"""
        SELECT DISTINCT p.* FROM planetes p
        WHERE {' AND '.join(conditions)}
        ORDER BY p.date_ajout DESC
    """
    
    cursor.execute(requete, params)
    resultats = cursor.fetchall()
    conn.close()
    
    planetes = []
    for r in resultats:
        planetes.append({
            "id": r[0],
            "nom_planete": r[1],
            "systeme": r[2],
            "position": r[3],
            "eau": r[4],
            "gravite": r[5],
            "temperature": r[6],
            "magnetisme": r[7],
            "vent_solaire": r[8],
            "atmosphere": r[9]
        })
    return planetes

def get_ressources_planete(planete_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT nom, pourcentage, efficacite FROM ressources WHERE planete_id = ?", (planete_id,))
    resultats = cursor.fetchall()
    conn.close()
    return [{"nom": r[0], "pourcentage": r[1], "efficacite": r[2]} for r in resultats]

# ==================== INTERFACE GRAPHIQUE ====================
class EmpireManager:
    def __init__(self, root):
        self.root = root
        self.root.title("🌍 Empire Universe 4 - Gestionnaire de Planètes")
        self.root.geometry("1600x760")
        self.root.configure(bg="#1e1e2e")
        
        self.race_actuelle = None
        self.planetes_resultats = []
        
        self.setup_ui()
        init_db()
    
    def setup_ui(self):
        # Panneau principal
        panneau = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        panneau.pack(fill=tk.BOTH, expand=True, padx=2, pady=10)
        
        # ===== GAUCHE (FIXE) =====
        frame_gauche = tk.Frame(panneau, width=320, bg="#1e1e2e")
        frame_gauche.pack_propagate(False)  # Empêche le redimensionnement automatique
        panneau.add(frame_gauche, weight=0)
        
        # Section Ajout (bouton qui ouvre une popup)
        btn_ajouter = tk.Button(frame_gauche, text="➕ Ajouter une planète", bg="#2ecc71", fg="white",
                                font=("Segoe UI", 11, "bold"), command=self.ouvrir_popup_ajout)
        btn_ajouter.pack(fill=tk.X, pady=(0,5))
       
        # Compteur de planètes
        self.label_compteur = tk.Label(frame_gauche, text="", font=("Segoe UI", 9), bg="#1e1e2e", fg="#aaaaaa")
        self.label_compteur.pack(anchor=tk.CENTER, fill=tk.X, pady=(0,5))
        self.mettre_a_jour_compteur()

        # Import export :
        frame_export_import = tk.Frame(frame_gauche, bg="#1e1e2e")
        frame_export_import.pack(fill=tk.X, pady=(10,5))

        btn_export = tk.Button(frame_export_import, text="📤 Exporter", bg="#3498db", fg="white",
                                font=("Segoe UI", 9), command=self.exporter_base)
        btn_export.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        btn_import = tk.Button(frame_export_import, text="📥 Importer", bg="#2ecc71", fg="white",
                                font=("Segoe UI", 9), command=self.importer_base)
        btn_import.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        ttk.Separator(frame_gauche, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Section Recherche Ressources
        ttk.Label(frame_gauche, text="🔍 RECHERCHE PAR RESSOURCES", font=("Segoe UI", 12, "bold")).pack(anchor=tk.CENTER, fill=tk.X, pady=(0,5))
        
        self.frame_ressources = ttk.Frame(frame_gauche)
        self.frame_ressources.pack(fill=tk.X, pady=5)
        
        self.ressources_criteres = []
        self.ajouter_champ_ressource()
        
        btn_ajouter_ress = tk.Button(frame_gauche, text="+ Ajouter une ressource", bg="#3498db", fg="white",
                                    font=("Segoe UI", 9), command=self.ajouter_champ_ressource)
        btn_ajouter_ress.pack(anchor=tk.CENTER, fill=tk.X, pady=(5,10))
        
        ttk.Separator(frame_gauche, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Section recherche par système
        ttk.Label(frame_gauche, text="🔎 RECHERCHE PAR SYSTÈME", font=("Segoe UI", 11, "bold")).pack(anchor=tk.CENTER, fill=tk.X, pady=(0,5))

        frame_systeme = tk.Frame(frame_gauche, bg="#1e1e2e")
        frame_systeme.pack(fill=tk.X, pady=5)

        self.entry_systeme = tk.Entry(frame_systeme, font=("Segoe UI", 10), bg="#2d2d3d", fg="white", insertbackground="white")
        self.entry_systeme.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))

        btn_rechercher_systeme = tk.Button(frame_systeme, text="🔍", bg="#3498db", fg="white",
                                            font=("Segoe UI", 10), command=self.rechercher_par_systeme)
        btn_rechercher_systeme.pack(side=tk.RIGHT)
        
        ttk.Separator(frame_gauche, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Section Race
        ttk.Label(frame_gauche, text="👽 FILTRE RACIAL (optionnel)", font=("Segoe UI", 12, "bold")).pack(anchor=tk.CENTER, fill=tk.X, pady=(0,5))

        race_frame = ttk.Frame(frame_gauche)
        race_frame.pack(fill=tk.X, pady=5)

        ttk.Label(race_frame, text="Race :").pack(side=tk.LEFT)
        self.race_var = tk.StringVar()
        self.combo_race = ttk.Combobox(race_frame, textvariable=self.race_var, values=list(RACES.keys()), width=15)
        self.combo_race.pack(side=tk.LEFT, padx=(10,0))
        self.combo_race.bind("<<ComboboxSelected>>", self.on_race_selected)

        # Case à cocher
        self.show_details_var = tk.BooleanVar(value=False)
        self.show_details_check = ttk.Checkbutton(race_frame, text="Détails",
                                                variable=self.show_details_var,
                                                command=self.toggle_race_details)
        self.show_details_check.pack(side=tk.LEFT, padx=(10,0))

        # Détails race - CRÉER MAIS NE PAS PACKER TOUT DE SUITE
        self.frame_details_race = ttk.LabelFrame(frame_gauche, text="Détails de la race")
        self.labels_details = {}
        for champ in ["temperature", "gravite", "eau", "magnetisme", "vent_solaire", "atmosphere"]:
            self.labels_details[champ] = ttk.Label(self.frame_details_race, text="")
            self.labels_details[champ].pack(anchor=tk.W, padx=5, pady=2)

        # Ne pas packer frame_details_race ici ! On va le faire plus tard

        # Bouton Appliquer la race
        self.btn_appliquer_race = tk.Button(frame_gauche, text="🎯 Appliquer la race", bg="#9b59b6", fg="white",
                                     font=("Segoe UI", 10), command=self.appliquer_race)
        self.btn_appliquer_race.pack(fill=tk.X, pady=5)

        ttk.Separator(frame_gauche, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
    





        
        # Bouton Rechercher
        btn_rechercher = tk.Button(frame_gauche, text="🔎 RECHERCHER", bg="#e67e22", fg="white",
                                    font=("Segoe UI", 12, "bold"), command=self.rechercher)
        btn_rechercher.pack(fill=tk.X, pady=10)
        
        # ===== DROITE (REDIMENSIONNABLE) =====
        frame_droite = ttk.Frame(panneau)
        panneau.add(frame_droite, weight=1)  # Prend tout l'espace restant
        
        ttk.Label(frame_droite, text="📋 RÉSULTATS", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W, pady=(0,5))
        
        # Canvas + Scrollbar pour les résultats
        canvas = tk.Canvas(frame_droite, bg="#1e1e2e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame_droite, orient=tk.VERTICAL, command=canvas.yview)
        self.frame_resultats = ttk.Frame(canvas)
        
        self.frame_resultats.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.frame_resultats, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Scroll avec la molette
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)

    def ouvrir_popup_ajout(self):
        """Ouvre une fenêtre popup pour coller le rapport de sonde"""
        popup = tk.Toplevel(self.root)
        popup.title("➕ Ajouter une planète")
        popup.geometry("600x500")
        popup.configure(bg="#1e1e2e")
        popup.transient(self.root)  # Liée à la fenêtre principale
        popup.grab_set()  # Modale
        
        # Centrer la popup
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (600 // 2)
        y = (popup.winfo_screenheight() // 2) - (500 // 2)
        popup.geometry(f"600x500+{x}+{y}")
        
        # Zone de texte
        ttk.Label(popup, text="📡 Colle le rapport de la sonde :", font=("Segoe UI", 11, "bold")).pack(pady=(15,5))
        
        zone_texte = tk.Text(popup, height=20, font=("Consolas", 9), bg="#2d2d3d", fg="#ffffff", insertbackground="white")
        zone_texte.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        zone_texte.focus_set()

        # Boutons
        frame_boutons = tk.Frame(popup, bg="#1e1e2e")
        frame_boutons.pack(fill=tk.X, padx=15, pady=10)
                
        def ajouter():
            texte = zone_texte.get("1.0", tk.END).strip()
            if not texte:
                messagebox.showwarning("Avertissement", "Colle un rapport de sonde d'abord")
                return
            try:
                donnees = parser_rapport_sonde(texte)
                
                # Vérifier si la planète existe déjà
                if self.planete_existe(donnees['systeme'], donnees['position']):
                    reponse = messagebox.askyesno(
                        "Planète existante",
                        f"La planète {donnees['systeme']} {donnees['position']} existe déjà.\n\n"
                        "Veux-tu la remplacer (écraser) ?\n"
                        "- Oui : remplace l'ancienne\n"
                        "- Non : annule l'ajout"
                    )
                    if reponse:
                        # Supprimer l'ancienne planète (et ses ressources)
                        conn = sqlite3.connect(DB_FILE)
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM ressources WHERE planete_id IN (SELECT id FROM planetes WHERE systeme = ? AND position = ?)", 
                                    (donnees['systeme'], donnees['position']))
                        cursor.execute("DELETE FROM planetes WHERE systeme = ? AND position = ?", 
                                    (donnees['systeme'], donnees['position']))
                        conn.commit()
                        conn.close()
                    else:
                        return  # Annule l'ajout
                
                # Ajouter la planète
                ajouter_planete(donnees)
                self.mettre_a_jour_compteur()
                messagebox.showinfo("Succès", f"✅ Planète {donnees['systeme']} {donnees['position']} ajoutée !")
                popup.destroy()
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible d'ajouter: {str(e)}")





        btn_ajouter = tk.Button(frame_boutons, text="✅ Ajouter", bg="#2ecc71", fg="white",
                                font=("Segoe UI", 10, "bold"), command=ajouter)
        btn_ajouter.pack(side=tk.LEFT, padx=5)
        
        btn_annuler = tk.Button(frame_boutons, text="❌ Annuler", bg="#e74c3c", fg="white",
                                font=("Segoe UI", 10), command=popup.destroy)
        btn_annuler.pack(side=tk.LEFT, padx=5)

    def planete_existe(self, systeme, position):
        """Vérifie si une planète existe déjà dans la base"""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM planetes WHERE systeme = ? AND position = ?", (systeme, position))
        resultat = cursor.fetchone()
        conn.close()
        return resultat is not None

    def ajouter_champ_ressource(self):
        frame = ttk.Frame(self.frame_ressources)
        frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(frame, text="Ressource:").pack(side=tk.LEFT)
        
        ressources_liste = ["Titane", "Cuivre", "Aluminium", "Silicium", "Fer", "Mercure", "Uranium", "Krypton", "Azote", "Hydrogène"]
        combo = ttk.Combobox(frame, values=ressources_liste, width=12)
        combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(frame, text="≥").pack(side=tk.LEFT)
        entry = tk.Entry(frame, width=5)
        entry.insert(0, "50")
        entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(frame, text="%").pack(side=tk.LEFT)
        
        btn_suppr = tk.Button(frame, text="✖", bg="#e74c3c", fg="white", font=("Segoe UI", 8),
                               command=lambda: self.supprimer_champ_ressource(frame))
        btn_suppr.pack(side=tk.RIGHT, padx=5)
        
        self.ressources_criteres.append({"frame": frame, "combo": combo, "entry": entry})
    
    def supprimer_champ_ressource(self, frame):
        for i, crit in enumerate(self.ressources_criteres):
            if crit["frame"] == frame:
                frame.destroy()
                del self.ressources_criteres[i]
                break
    
    def get_criteres_ressources(self):
        criteres = []
        for crit in self.ressources_criteres:
            nom = crit["combo"].get()
            try:
                min_val = float(crit["entry"].get())
                if nom and min_val > 0:
                    criteres.append({"nom": nom, "min_pourcentage": min_val})
            except:
                pass
        return criteres
    
    def rechercher_par_systeme(self):
        """Recherche les planètes dont le système correspond"""
        systeme = self.entry_systeme.get().strip()
        if not systeme:
            messagebox.showwarning("Avertissement", "Entre un numéro de système")
            return
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT id, nom_planete, systeme, position, eau, gravite, temperature, magnetisme, vent_solaire, atmosphere FROM planetes WHERE systeme LIKE ? ORDER BY date_ajout DESC", (f"%{systeme}%",))
        resultats = cursor.fetchall()
        conn.close()
        
        self.planetes_resultats = []
        for r in resultats:
            self.planetes_resultats.append({
                "id": r[0],
                "nom_planete": r[1],
                "systeme": r[2],
                "position": r[3],
                "eau": r[4],
                "gravite": r[5],
                "temperature": r[6],
                "magnetisme": r[7],
                "vent_solaire": r[8],
                "atmosphere": r[9]
            })
        
        self.rafraichir_affichage()

    def on_race_selected(self, event=None):
        race = self.race_var.get()
        if race not in RACES:
            return
        
        criteres = RACES[race]["criteria"]
        
        labels = {
            "temperature": "🌡️Température",
            "gravite": "⚡    Gravité",
            "eau": "💧     Eau",
            "magnetisme": "🧲     Magnétisme",
            "vent_solaire": "🌬️Vent Solaire",
            "atmosphere": "🌫️Atmosphère"
        }
        
        for champ, label in labels.items():
            if champ in criteres:
                min_val = criteres[champ]["min"]
                max_val = criteres[champ]["max"]
                weight = criteres[champ]["weight"]
                self.labels_details[champ].config(text=f"{label} : {min_val} - {max_val} (poids {weight}%)")
            else:
                self.labels_details[champ].config(text=f"{label} : non utilisé")
    
    def toggle_race_details(self):
        """Affiche ou cache les détails de la race selon la checkbox"""
        if self.show_details_var.get():
            # Packer APRÈS race_frame MAIS AVANT btn_appliquer_race
            self.frame_details_race.pack(fill=tk.X, pady=(5,5), before=self.btn_appliquer_race)
            if self.race_var.get():
                self.on_race_selected()
        else:
            self.frame_details_race.pack_forget()

    def appliquer_race(self):
        race = self.race_var.get()
        if not race or race not in RACES:
            messagebox.showwarning("Avertissement", "Sélectionne une race d'abord")
            return
        
        self.race_actuelle = RACES[race]["criteria"]
        self.rafraichir_affichage()
    
    def rafraichir_affichage(self):
        # Effacer les résultats actuels
        for widget in self.frame_resultats.winfo_children():
            widget.destroy()
        
        if not self.planetes_resultats:
            ttk.Label(self.frame_resultats, text="Aucune planète trouvée").pack(pady=20)
            return
        
        for planete in self.planetes_resultats:
            self.afficher_planete(planete)
    
    def afficher_planete(self, planete):
        # Frame pour une planète
        frame_planete = tk.Frame(self.frame_resultats, bg="#2d2d3d", relief=tk.RAISED, bd=1)
        frame_planete.pack(fill=tk.X, pady=5, padx=5)
        
       # Ligne 0 : Titre + Boutons
        ligne_titre = tk.Frame(frame_planete, bg="#2d2d3d")
        ligne_titre.pack(fill=tk.X, padx=10, pady=(5,0))

        # Bouton Note à gauche
        btn_note = tk.Button(ligne_titre, text="📝", font=("Segoe UI", 11), 
                            bg="#2d2d3d", fg="#f39c12", bd=0, cursor="hand2",
                            command=lambda: self.ajouter_note(planete))
        btn_note.pack(side=tk.LEFT, padx=(0,5))
        ToolTip(btn_note, "Ajouter/Modifier une note")

        # Nom de la planète (si existe)
        if planete.get("nom_planete") and planete["nom_planete"]:
            nom_affichage = planete["nom_planete"]
            tk.Label(ligne_titre, text=nom_affichage, font=("Segoe UI", 11, "bold"), 
                    bg="#2d2d3d", fg="#ffffff").pack(side=tk.LEFT, padx=(0,5))
            
        # Titre (coordonnées)
        titre = f"🌍 {planete['systeme']} {planete['position']}"
        tk.Label(ligne_titre, text=titre, font=("Segoe UI", 11, "bold"), 
                bg="#2d2d3d", fg="#ffffff").pack(side=tk.LEFT)
        
        # Récupérer la note existante
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT notes FROM planetes WHERE id = ?", (planete["id"],))
        resultat = cursor.fetchone()
        note = resultat[0] if resultat and resultat[0] else ""
        conn.close()

        # Si une note existe, l'afficher à droite du titre
        if note:
            # Tronquer la note si elle est trop longue (optionnel)
            note_affichage = note[:30] + "..." if len(note) > 30 else note
            label_note = tk.Label(ligne_titre, text=f"💬 {note_affichage}", 
                                font=("Segoe UI", 9, "italic"),
                                bg="#2d2d3d", fg="#aaaaaa")
            label_note.pack(side=tk.LEFT, padx=(10,0))
            
            # Tooltip pour voir la note complète au survol
            # ToolTip(label_note, note)

        # Bouton Supprimer (X) tout à droite
        btn_suppr = tk.Button(ligne_titre, text="❌", font=("Segoe UI", 9),
                            bg="#2d2d3d", fg="#e74c3c", bd=0,
                            command=lambda: self.supprimer_planete(planete))
        btn_suppr.pack(side=tk.RIGHT, padx=(5,0))
        
        # Ligne 2 : Caractéristiques
        frame_caracs = tk.Frame(frame_planete, bg="#2d2d3d")
        frame_caracs.pack(anchor=tk.W, padx=10, pady=5)
        
        caracs = [
            ("Température", planete["temperature"], "temperature"),
            ("Gravité", planete["gravite"], "gravite"),
            ("Eau", planete["eau"], "eau"),
            ("Magnétisme", planete["magnetisme"], "magnetisme"),
            ("Vent Solaire", planete["vent_solaire"], "vent_solaire"),
            ("Atmosphère", planete["atmosphere"], "atmosphere")
        ]
        
        for i, (nom, valeur, champ) in enumerate(caracs):
            couleur = COLORS["neutre"]
            if self.race_actuelle and champ in self.race_actuelle:
                min_val = self.race_actuelle[champ]["min"]
                max_val = self.race_actuelle[champ]["max"]
                couleur = get_race_color(float(valeur), min_val, max_val)
            
            label = tk.Label(frame_caracs, text=f"{nom}: {valeur}", bg="#2d2d3d", fg="#ffffff", font=("Segoe UI", 9))
            label.pack(side=tk.LEFT, padx=5)
            
            # Bulle de couleur
            bulle = tk.Label(frame_caracs, text="●", fg=couleur, bg="#2d2d3d", font=("Segoe UI", 9))
            bulle.pack(side=tk.LEFT)
            
            if i < len(caracs) - 1:
                tk.Label(frame_caracs, text="│", bg="#2d2d3d", fg="#666666").pack(side=tk.LEFT, padx=5)
        
        # Ligne 3 : Ressources
        ressources = get_ressources_planete(planete["id"])
        frame_ress = tk.Frame(frame_planete, bg="#2d2d3d")
        frame_ress.pack(anchor=tk.W, padx=10, pady=(0,10))
        
        tk.Label(frame_ress, text="📦", bg="#2d2d3d", fg="#ffffff", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        
        for i, res in enumerate(ressources):
            pourcentage = res["pourcentage"]
            couleur = get_ressource_color(pourcentage)
            
            label = tk.Label(frame_ress, text=f"{res['nom']}: {pourcentage}%", bg="#2d2d3d", fg="#ffffff", font=("Segoe UI", 9))
            label.pack(side=tk.LEFT, padx=2)
            
            bulle = tk.Label(frame_ress, text="●", fg=couleur, bg="#2d2d3d", font=("Segoe UI", 9))
            bulle.pack(side=tk.LEFT)
            
            if i < len(ressources) - 1:
                tk.Label(frame_ress, text="│", bg="#2d2d3d", fg="#666666").pack(side=tk.LEFT, padx=2)
    
    def ajouter_note(self, planete):
        """Ouvre une petite popup pour ajouter une note"""
        popup = tk.Toplevel(self.root)
        popup.title(f"Note - {planete['systeme']} {planete['position']}")
        popup.geometry("350x200")
        popup.configure(bg="#1e1e2e")
        popup.transient(self.root)
        popup.grab_set()
        
        ttk.Label(popup, text="📝 Note :", font=("Segoe UI", 10)).pack(pady=(10,5))
        
        zone_note = tk.Text(popup, height=6, font=("Segoe UI", 10), bg="#2d2d3d", fg="#ffffff")
        zone_note.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Récupérer note existante
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT notes FROM planetes WHERE id = ?", (planete["id"],))
        resultat = cursor.fetchone()
        if resultat and resultat[0]:
            zone_note.insert("1.0", resultat[0])
        conn.close()
        
        def sauvegarder():
            note = zone_note.get("1.0", tk.END).strip()
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("UPDATE planetes SET notes = ? WHERE id = ?", (note, planete["id"]))
            conn.commit()
            conn.close()
            popup.destroy()
            self.rafraichir_affichage()

        btn_save = tk.Button(popup, text="💾 Sauvegarder", bg="#2ecc71", fg="white", command=sauvegarder)
        btn_save.pack(pady=10)

    def supprimer_planete(self, planete):
        """Supprime une planète après confirmation"""
        if messagebox.askyesno("Confirmation", f"Supprimer {planete['systeme']} {planete['position']} ?"):
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ressources WHERE planete_id = ?", (planete["id"],))
            cursor.execute("DELETE FROM planetes WHERE id = ?", (planete["id"],))
            conn.commit()
            conn.close()
            self.mettre_a_jour_compteur()
            self.rechercher()

    def rechercher(self):
        criteres_ress = self.get_criteres_ressources()
        self.planetes_resultats = rechercher_planetes(criteres_ress)
        self.rafraichir_affichage()

    def get_nb_planetes(self):
        """Retourne le nombre de planètes en base"""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Vérifier si la table existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='planetes'")
        if cursor.fetchone() is None:
            # La table n'existe pas → base vide
            conn.close()
            return 0
        
        cursor.execute("SELECT COUNT(*) FROM planetes")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def mettre_a_jour_compteur(self):
        """Met à jour l'affichage du nombre de planètes"""
        nb = self.get_nb_planetes()
        if nb == 0:
            self.label_compteur.config(text="📀 Aucune planète en mémoire")
        elif nb == 1:
            self.label_compteur.config(text="📀 1 planète en mémoire")
        else:
            self.label_compteur.config(text=f"📀 {nb} planètes en mémoire")

    def exporter_base(self):
        """Exporte toutes les planètes dans un fichier JSON"""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Récupérer toutes les planètes
        cursor.execute("SELECT * FROM planetes")
        planetes = cursor.fetchall()
        
        # Récupérer les ressources
        cursor.execute("SELECT * FROM ressources")
        ressources = cursor.fetchall()
        
        conn.close()
        
        data = {
            "version": "1.0",
            "date": datetime.now().isoformat(),
            "planetes": planetes,
            "ressources": ressources
        }
        
        filename = f"export_planetes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        
        messagebox.showinfo("Export", f"✅ Export réussi !\n📁 Fichier : {filename}")

    def importer_base(self):
        """Importe un fichier JSON et fusionne avec la base existante"""
        from tkinter import filedialog
        
        filename = filedialog.askopenfilename(
            title="Sélectionne un fichier d'export",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        nb_ajoutees = 0
        nb_ignorees = 0
        
        for planete in data["planetes"]:
            systeme = planete[1]
            position = planete[2]
            
            # Vérifier si la planète existe déjà
            cursor.execute("SELECT id FROM planetes WHERE systeme = ? AND position = ?", (systeme, position))
            if cursor.fetchone():
                nb_ignorees += 1
                continue
            
            # Insérer la planète
            cursor.execute('''
                INSERT INTO planetes (id, systeme, position, eau, gravite, temperature, 
                                    magnetisme, vent_solaire, atmosphere, date_ajout)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', planete)
            nb_ajoutees += 1
        
        # Mettre à jour les IDs auto-incrément
        cursor.execute("UPDATE sqlite_sequence SET seq = (SELECT MAX(id) FROM planetes) WHERE name = 'planetes'")
        
        # Insérer les ressources (avec les IDs recalculés)
        for ressource in data["ressources"]:
            planete_id = ressource[1]
            cursor.execute('''
                INSERT INTO ressources (planete_id, nom, pourcentage, efficacite)
                VALUES (?, ?, ?, ?)
            ''', (ressource[1], ressource[2], ressource[3], ressource[4]))
        
        conn.commit()
        conn.close()
        
        self.mettre_a_jour_compteur()
        messagebox.showinfo("Import", f"✅ Import terminé !\n📀 {nb_ajoutees} planète(s) ajoutée(s)\n⏭️ {nb_ignorees} ignorée(s) (doublons)")

# ==================== LANCEMENT ====================
if __name__ == "__main__":
    root = tk.Tk()
    app = EmpireManager(root)
    root.mainloop()
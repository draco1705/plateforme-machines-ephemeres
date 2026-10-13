# Guide Démonstration Pratique — Mode Cluster Multi-VM
**Projet 2 : Plateforme de Machines Éphémères**  
*Gestion automatisée de conteneurs Docker distribués*

---

## 🏗️ Architecture du Cluster

Le cluster est composé de 4 machines virtuelles VirtualBox orchestrées avec **Vagrant** et provisionnées avec **Ansible** :
- **Controller (`192.168.56.10`)** : Héberge le **Control Plane** (API FastAPI port 8000, base PostgreSQL, reverse proxy Traefik HTTPS avec certificats TLS wildcard `*.lab.local`, et daemon Scheduler avec boucle d'auto-guérison). *Aucun conteneur étudiant ne tourne sur le Controller.*
- **Workers (`192.168.56.11`, `.12`, `.13`)** : Hébergent le **Data Plane** (Agent Worker FastAPI sur le port 8001 envoyant des heartbeats toutes les 5s et moteur Docker exécutant les conteneurs isolés).

---

## ⚡ Préparation Initiale dans le Terminal

Ouvrez un terminal **PowerShell** sur votre machine hôte Windows dans le répertoire du projet :
```powershell
# Définir l'URL de l'API Controller et le chemin de l'exécutable Python
$env:LABHACKER_API_URL = "http://192.168.56.10:8000"
$python = ".\api\.venv\Scripts\python.exe"
```

---

## 📋 Scénario de Présentation Étape par Étape

### Étape 1 : Présentation de l'infrastructure et de la topologie

#### 1.1 Vérifier que les 4 VMs sont en cours d'exécution
```powershell
vagrant status
```
> **À dire au professeur :**  
> *"Nos 4 VMs sont opérationnelles. Le Controller isole la logique de contrôle et les 3 Workers exécutent les environnements étudiants sur un réseau privé 192.168.56.0/24."*

#### 1.2 Afficher l'état en temps réel des Workers (Heartbeats)
```powershell
& $python cli/labctl.py login admin@lab.local admin12345
& $python cli/labctl.py workers
```
*Affiche un tableau clair avec : Nom, IP, Statut (`AVAILABLE`/`BUSY`), CPU utilisé/total, RAM et nombre max de conteneurs.*
> **À dire au professeur :**  
> *"Voici notre commande `labctl workers`. Chaque worker transmet ses métriques toutes les 5 secondes via des heartbeats à l'API. Le Scheduler s'appuie sur ces métriques pour son algorithme de placement 'Best-Fit'."*

---

### Étape 2 : Authentification et Catalogue (Slide 8 - Étape 1 & 2)

#### 2.1 Connexion en tant qu'étudiant
```powershell
& $python cli/labctl.py login user@lab.local user12345
```
> **À dire au professeur :**  
> *"L'API authentifie l'utilisateur via mot de passe haché (bcrypt) et délivre un token JWT sécurisé qui sera transmis dans chaque requête."*

#### 2.2 Consultation du catalogue des machines disponibles
```powershell
& $python cli/labctl.py machines
```
> **À dire au professeur :**  
> *"Nous proposons plusieurs environnements préconfigurés : Nginx pour du test web, Alpine pour des tests légers, et Kali Linux avec serveur OpenSSH pour les TP de cybersécurité."*

---

### Étape 3 : Réservation & Déploiement Dynamique (Slide 8 - Étape 2 & 3)

#### 3.1 Créer une réservation (Exemple : Nginx pour 30 minutes)
```powershell
& $python cli/labctl.py reserve --machine nginx --duration 30
```
*Affiche : `✓ Réservation #<ID> créée (status: PENDING)`*

#### 3.2 Suivre le cycle de vie de la réservation
```powershell
& $python cli/labctl.py list
```
*En 2 à 3 secondes, le statut passe de `PENDING` à `RUNNING`, affichant le Worker assigné (ex: `1`, `2` ou `3`) et l'URL HTTPS `https://lab-<ID>.lab.local`.*

#### 3.3 Inspecter les détails complets de la réservation
```powershell
& $python cli/labctl.py status <ID>
```
*(Remplacez `<ID>` par le numéro de votre réservation, ex: `6`)*

#### 3.4 Preuve d'isolation sur le Worker
Vérifiez sur la VM Worker qui a reçu la réservation (remplacez `workerX` par `worker1`, `worker2` ou `worker3`) :
```powershell
vagrant ssh worker2 -c "docker ps"
```
> **À dire au professeur :**  
> *"Le conteneur tourne bien physiquement sur le Worker assigné et non sur le Controller, garantissant une stricte isolation."*

---

### Étape 4 : Accès et Exécution à Distance (Slide 8 - Étape 3)

#### 4.1 Exécution de commandes dans le conteneur distant (`labctl exec`)
Exécutez une commande système dans le conteneur à travers le cluster :
```powershell
& $python cli/labctl.py exec <ID> uname -a
& $python cli/labctl.py exec <ID> hostname
```
> **À dire au professeur :**  
> *"Le CLI envoie la commande au Control Plane, qui la relaie à l'agent du bon Worker. La sortie est renvoyée en temps réel dans notre terminal."*

#### 4.2 Test de connectivité Web sécurisée via Traefik (TLS / HTTPS)
```powershell
curl -k -I https://192.168.56.10/ -H "Host: lab-<ID>.lab.local"
```
*Affiche `HTTP/2 200 OK` avec le certificat de Traefik.*
> **À dire au professeur :**  
> *"Traefik gère le routage dynamique et le chiffrement TLS avec des certificats wildcard `*.lab.local` sans aucun redémarrage de service."*

---

### Étape 5 : Haute Disponibilité & Auto-Guérison (US43–US45)

> **Point fort de la présentation : panne matérielle et migration automatique.**

#### 5.1 Identifier le worker hébergeant la réservation
```powershell
& $python cli/labctl.py list
```
*(Supposons que la réservation active tourne sur `worker2`)*

#### 5.2 Simuler un crash matériel brutal du worker
```powershell
vagrant halt worker2
```
> **À dire au professeur :**  
> *"Je simule une panne matérielle en coupant brutalement la machine `worker2`."*

#### 5.3 Observer l'auto-détection et la replanification (Auto-Healing)
Attendez environ 30 secondes (délai de détection de perte de heartbeat), puis affichez l'historique d'audit des événements :
```powershell
& $python -c "
import os, requests
tok = open(os.path.expanduser('~/.labhacker_token')).read().strip()
events = requests.get('http://192.168.56.10:8000/reservations/<ID>/events', headers={'Authorization': 'Bearer ' + tok}).json()
print('{:<25} {:<12} {:<12} {:<40}'.format('DATE/HEURE', 'DE', 'VERS', 'RAISON'))
print('-' * 95)
for e in events:
    print('{:<25} {:<12} {:<12} {:<40}'.format(e['created_at'][:19], str(e['from_status']), e['to_status'], str(e['reason'])))
"
```
*On observe la séquence automatique :*
1. `PENDING -> RUNNING (assigned_to_worker_worker2)`
2. `RUNNING -> RUNNING (auto_repair_started: worker_worker2_offline)`
3. `RUNNING -> RUNNING (auto_repaired_on_worker1)`

#### 5.4 Vérifier la réapparition du conteneur sur le nouveau worker
```powershell
vagrant ssh worker1 -c "docker ps"
```
> **À dire au professeur :**  
> *"Le conteneur a été automatiquement migré et redémarré sur un nœud sain sans aucune intervention humaine."*

#### 5.5 Rallumer la machine virtuelle
```powershell
vagrant up worker2
```

---

### Étape 6 : Fin de Réservation et Nettoyage des Ressources (Slide 8 - Étape 4)

#### 6.1 Annuler manuellement la réservation
```powershell
& $python cli/labctl.py delete <ID>
```
*Affiche : `✓ Réservation #<ID> annulée`*

#### 6.2 Vérifier la libération immédiate des quotas
```powershell
& $python cli/labctl.py list
& $python cli/labctl.py workers
```
*Le statut passe à `CANCELLED`, le conteneur est détruit et les ressources CPU/RAM du worker sont à nouveau à 0.*

---

## 💡 Fiche Récapitulative des Commandes pour la Démo

| Action | Commande |
| :--- | :--- |
| **Variables d'environnement** | `$env:LABHACKER_API_URL = "http://192.168.56.10:8000" ; $python = ".\api\.venv\Scripts\python.exe"` |
| **Statut des VMs** | `vagrant status` |
| **État des Workers** | `& $python cli/labctl.py workers` |
| **Connexion étudiant** | `& $python cli/labctl.py login user@lab.local user12345` |
| **Catalogue machines** | `& $python cli/labctl.py machines` |
| **Créer réservation** | `& $python cli/labctl.py reserve --machine nginx --duration 30` |
| **Lister réservations** | `& $python cli/labctl.py list` |
| **Détails réservation** | `& $python cli/labctl.py status <ID>` |
| **Exécuter commande** | `& $python cli/labctl.py exec <ID> uname -a` |
| **Test HTTPS Traefik** | `curl -k -I https://192.168.56.10/ -H "Host: lab-<ID>.lab.local"` |
| **Crash d'un worker** | `vagrant halt workerX` |
| **Historique / Audit** | Appel API `GET /reservations/<ID>/events` |
| **Rallumer le worker** | `vagrant up workerX` |
| **Annuler réservation** | `& $python cli/labctl.py delete <ID>` |

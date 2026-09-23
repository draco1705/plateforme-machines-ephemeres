# Plateforme Machines Éphémères
 Plateforme permettant de déployer et gérer des machines éphémères à l'aide de Docker, Vagrant et Ansible.
 ## Prérequis
 - Python 3
- Docker
- Docker Compose
- Vagrant
- Ansible

 ## Installation

 ### Windows

 Depuis le dossier du projet :

```
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
```

 Le script crée `.venv` et installe les dépendances de `requirements.txt`.

 Activer l'environnement :

```
.\.venv\Scripts\Activate.ps1
```

 ### Linux

 Depuis le dossier du projet :

```
chmod +x install.sh
./install.sh
```

 Le script crée `.venv` et installe les dépendances de `requirements.txt`.

 Activer l'environnement :

```
source .venv/bin/activate
```

 ## Installation manuelle

```
pip install -r requirements.txt
```

 ## Vérification

```
python --version
pip list
docker --version
docker compose version
vagrant --version
ansible --version
```
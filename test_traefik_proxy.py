import time
import httpx
import docker
import sys

def run_tests():
    print("=== DÉBUT DES TESTS TRAEFIK (Reverse Proxy) ===")
    
    # 1. Préparation
    client = docker.from_env()
    reservation_id = 9999
    host = f"lab-{reservation_id}.lab.local"
    
    labels = {
        "traefik.enable": "true",
        f"traefik.http.routers.lab-{reservation_id}-http.rule": f"Host(`{host}`)",
        f"traefik.http.routers.lab-{reservation_id}-http.entrypoints": "web",
        f"traefik.http.routers.lab-{reservation_id}-http.middlewares": "redirect-to-https@file",
        
        f"traefik.http.routers.lab-{reservation_id}.rule": f"Host(`{host}`)",
        f"traefik.http.routers.lab-{reservation_id}.entrypoints": "websecure",
        f"traefik.http.routers.lab-{reservation_id}.tls": "true",
        f"traefik.http.routers.lab-{reservation_id}.middlewares": "security-headers@file",
        
        f"traefik.http.services.lab-{reservation_id}.loadbalancer.server.port": "80"
    }
    
    print(f"\n[+] Création d'un conteneur de test (Reservation ID: {reservation_id})...")
    try:
        container = client.containers.run(
            "traefik/whoami",
            name=f"lab-reservation-{reservation_id}",
            detach=True,
            network="lab-net",
            labels=labels
        )
    except Exception as e:
        print(f"Erreur lors de la création du conteneur: {e}")
        sys.exit(1)
        
    try:
        # Attendre que Traefik détecte le conteneur
        print("[+] Attente de la détection par Traefik...")
        time.sleep(3)
        
        # 1. Détection dynamique (US25/US26)
        print("\n--- TEST 1: Détection dynamique (API Traefik) ---")
        api_url = f"http://localhost:8080/api/http/routers/lab-{reservation_id}@docker"
        r = httpx.get(api_url)
        assert r.status_code == 200, f"Le routeur Traefik n'a pas été trouvé (Status {r.status_code})"
        print("[OK] Traefik a bien détecté le nouveau routeur.")
        
        # 2. Sécurité & TLS (US27)
        print("\n--- TEST 2: Redirection HTTP -> HTTPS ---")
        headers = {"Host": host}
        
        # On désactive les redirects automatiques pour vérifier le code 301/308
        r_http = httpx.get("http://localhost/", headers=headers, follow_redirects=False)
        assert r_http.status_code in [301, 308, 302, 307], f"Pas de redirection HTTP vers HTTPS (Status {r_http.status_code})"
        print(f"[OK] Redirection HTTP -> HTTPS fonctionnelle (Code: {r_http.status_code}).")
        
        print("\n--- TEST 3: Connexion HTTPS et En-têtes de sécurité ---")
        # Désactiver la vérification SSL car c'est un certificat auto-signé
        r_https = httpx.get("https://localhost/", headers=headers, verify=False)
        assert r_https.status_code == 200, f"L'accès HTTPS a échoué (Status {r_https.status_code})"
        print("[OK] Connexion HTTPS (port 443) établie avec succès (Code 200).")
        
        # Vérification des en-têtes de sécurité (injectés par le middleware security-headers)
        hsts = r_https.headers.get("Strict-Transport-Security")
        ctype_opts = r_https.headers.get("X-Content-Type-Options")
        print(f"  - Strict-Transport-Security: {hsts}")
        print(f"  - X-Content-Type-Options: {ctype_opts}")
        
        # 3. Nettoyage & Cycle de vie
        print("\n--- TEST 4: Nettoyage et suppression ---")
        print("[+] Arrêt et suppression du conteneur...")
        container.stop(timeout=2)
        container.remove()
        
        time.sleep(3) # Laisser le temps à Traefik de mettre à jour sa config
        
        r_deleted = httpx.get("https://localhost/", headers=headers, verify=False)
        assert r_deleted.status_code == 404, f"La route existe toujours après suppression (Status {r_deleted.status_code})"
        print("[OK] Route correctement purgée après la suppression du conteneur (Erreur 404).")
        
        print("\n*** TOUS LES TESTS SONT PASSÉS AVEC SUCCÈS ! ***")
        
    except AssertionError as e:
        print(f"\n[FAIL] ÉCHEC DU TEST: {e}")
        # Nettoyage en cas d'erreur
        container.stop(timeout=1)
        container.remove()
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] ERREUR INATTENDUE: {e}")
        container.stop(timeout=1)
        container.remove()
        sys.exit(1)

if __name__ == "__main__":
    run_tests()

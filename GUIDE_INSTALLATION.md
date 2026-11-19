# Swamp Replay — installation du robot (une seule fois, ≈ 20 min)

Même principe que Crossover Arena. **Aucune clé dans le chat** : tu les ranges toi-même aux endroits indiqués.

## 1. Bot Telegram
Si ce n'est pas déjà fait : @BotFather → `/newbot` → nom `Swamp Replay Robot`, pseudo par ex. `swamp_replay_bot`.
Ouvre le bot et appuie sur **Démarrer** (sinon « chat not found »).

## 2. Mettre le dépôt sur GitHub
1. **GitHub Desktop** → File → **Add local repository** → `D:\ZONE IA\CLAUDE_DB\GTA6Clips\swamp-replay`
   (s'il propose « create a repository », accepte).
2. Message `Swamp Replay : robot` → **Commit to main** → **Publish repository**.
3. **Décoche « Keep this code private »** : le dépôt doit être **public** (il héberge les vidéos pour Buffer, aucun secret dedans).

## 3. Ranger les clés sur GitHub
github.com → dépôt `swamp-replay` → **Settings → Secrets and variables → Actions → New repository secret** :

| Nom (exact) | Valeur |
|---|---|
| `TELEGRAM_BOT_TOKEN` | jeton du bot Swamp Replay |
| `TELEGRAM_CHAT_ID` | ton identifiant Telegram (@userinfobot) |
| `BUFFER_API_KEY` | clé du **3e** compte Buffer |
| `CLOUDFLARE_API_TOKEN` | jeton Cloudflare, modèle **Edit Cloudflare Workers** |

## 4. Clé du PC
1. github.com → photo de profil → **Settings → Developer settings → Fine-grained tokens → Generate new token**.
2. Nom `PC Swamp Replay` · 1 an · **Only select repositories → swamp-replay** · **Contents : Read and write**.
3. Ouvre `D:\ZONE IA\CLAUDE_DB\GTA6Clips\secrets_pc.env` avec le Bloc-notes, remplis les 4 lignes, enregistre
   (attention : le nom doit rester `secrets_pc.env`, pas `.env.txt`).

## 5. Allumer et tester
1. **Actions → Installer le réceptionniste → Run workflow** → « ✅ Réceptionniste installé » sur Telegram.
2. **Actions → Tester les connexions → Run workflow** : Telegram ✅, Buffer ✅ (tiktok, youtube, instagram), Hébergement ✅.
3. Dis « c'est fait » : je dépose un clip de **TEST**, tu appuies sur ✅, Buffer crée 3 brouillons (rien n'est publié).

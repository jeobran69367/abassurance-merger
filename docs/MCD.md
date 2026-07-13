# Modèle Conceptuel de Données (MCD) unifié

## 1. Principe de mapping

Les deux bases sources (`AbAssurance` / Oracle et `AssurePlus` / SQL Server) modélisent le même
domaine métier (client, contrat, sinistre, paiement) avec des conventions différentes. Le modèle
cible **conserve les identifiants sources** (traçabilité réglementaire) et ajoute une clé
technique unifiée + un champ `source_system`, indispensable pour la fusion sans perte
d'information (exigence de continuité réglementaire et contractuelle du cahier des charges).

| Entité cible | Table Oracle (AB_*)        | Table SQL Server (AP_*) |
|--------------|-----------------------------|--------------------------|
| CLIENT       | AB_CLIENT                   | AP_USERS                |
| CONTRAT      | AB_CONTRAT                  | AP_CONTRACTS             |
| SINISTRE     | AB_SINISTRE                 | AP_CLAIMS                |
| PAIEMENT     | AB_PAIEMENT                 | AP_PAYMENTS               |

## 2. Entités du modèle cible

### CLIENT
| Champ unifié        | Type          | Origine AB_CLIENT      | Origine AP_USERS         |
|----------------------|---------------|--------------------------|----------------------------|
| client_id (PK)        | UUID/BIGINT   | AB_CLIENT_ID              | AP_USER_ID                  |
| source_system         | VARCHAR(10)   | 'ABASSURANCE'             | 'ASSUREPLUS'                 |
| source_id              | VARCHAR(30)   | AB_CLIENT_ID              | AP_USER_ID                   |
| nom                    | VARCHAR(100)  | AB_NOM                    | (split de AP_FULL_NAME)      |
| prenom                 | VARCHAR(100)  | AB_PRENOM                 | (split de AP_FULL_NAME)      |
| date_naissance         | DATE          | AB_DATE_NAISSANCE          | AP_BIRTH_DATE (parse YYYY-MM-DD) |
| email                   | VARCHAR(150)  | AB_EMAIL                  | AP_MAIL_ADDRESS               |
| telephone               | VARCHAR(20)   | AB_TELEPHONE               | AP_PHONE_NUMBER                |
| adresse                 | VARCHAR(255)  | AB_ADRESSE                 | AP_STREET_ADDRESS              |
| code_postal             | VARCHAR(10)   | AB_CODE_POSTAL             | AP_ZIP_CODE                    |
| date_creation           | TIMESTAMP     | AB_DATE_CREATION           | AP_CREATED_AT                   |
| statut_client            | VARCHAR(20)   | AB_STATUT_CLIENT            | AP_CUSTOMER_STATUS               |
| score_fidelite (nullable)| INT          | —                          | AP_LOYALTY_SCORE                 |
| num_fiscal (nullable)    | VARCHAR(30)  | AB_NUM_FISCAL              | — (absent côté AssurePlus)        |

### CONTRAT
| Champ unifié        | Type          | Origine AB_CONTRAT        | Origine AP_CONTRACTS        |
|----------------------|---------------|-----------------------------|--------------------------------|
| contrat_id (PK)       | UUID          | généré                      | généré                          |
| source_system          | VARCHAR(10)  | 'ABASSURANCE'                | 'ASSUREPLUS'                     |
| numero_police           | VARCHAR(30)  | AB_POLICY_NUMBER              | AP_CONTRACT_REF                    |
| client_id (FK)          | UUID         | via AB_CLIENT_ID               | via AP_USER_ID                       |
| type_produit             | VARCHAR(50)  | AB_TYPE_ASSURANCE              | AP_PRODUCT_CODE                       |
| date_debut                | DATE        | AB_DATE_DEBUT                   | AP_START_DATE                          |
| date_fin                    | DATE       | AB_DATE_FIN                      | AP_END_DATE                             |
| prime_periodique             | DECIMAL(10,2)| AB_PRIME_ANNUELLE (annuelle)   | AP_MONTHLY_PREMIUM (mensuelle × 12 à l'ingestion) |
| statut_contrat                | VARCHAR(20)| AB_STATUT_CONTRAT                | AP_CONTRACT_STATE                         |
| agence_ou_courtier              | VARCHAR(30)| AB_AGENCE_ID                     | AP_BROKER_CODE                             |

### SINISTRE
| Champ unifié       | Type           | Origine AB_SINISTRE        | Origine AP_CLAIMS            |
|---------------------|----------------|-------------------------------|----------------------------------|
| sinistre_id (PK)     | UUID           | généré                         | généré                            |
| source_system         | VARCHAR(10)   | 'ABASSURANCE'                   | 'ASSUREPLUS'                       |
| contrat_id (FK)         | UUID          | via AB_POLICY_NUMBER              | via AP_CONTRACT_REF                  |
| date_sinistre             | TIMESTAMP    | AB_DATE_SINISTRE                   | AP_INCIDENT_DATE (parse variable)      |
| montant_estime              | DECIMAL(12,2)| AB_MONTANT_ESTIME                  | AP_ESTIMATED_AMOUNT                     |
| statut_sinistre               | VARCHAR(30) | AB_STATUT_SINISTRE                  | AP_CLAIM_STATUS                          |
| description                     | TEXT       | AB_DESCRIPTION                       | AP_CLAIM_COMMENT                          |
| score_fraude (nullable)           | DECIMAL(5,2)| —                                    | AP_FRAUD_SCORE                              |

### PAIEMENT
| Champ unifié      | Type           | Origine AB_PAIEMENT       | Origine AP_PAYMENTS         |
|--------------------|----------------|------------------------------|---------------------------------|
| paiement_id (PK)    | UUID           | généré                        | généré                           |
| source_system         | VARCHAR(10)  | 'ABASSURANCE'                  | 'ASSUREPLUS'                      |
| contrat_id (FK)          | UUID        | via AB_POLICY_NUMBER              | via AP_CONTRACT_REF                  |
| date_paiement              | DATE       | AB_DATE_PAIEMENT                    | AP_PAYMENT_DATETIME                    |
| montant                       | DECIMAL(10,2)| AB_MONTANT                        | AP_AMOUNT_PAID                            |
| mode_paiement                   | VARCHAR(30)| AB_MODE_PAIEMENT                    | AP_PAYMENT_CHANNEL                          |
| statut_transaction (nullable)     | VARCHAR(20)| —                                  | AP_TRANSACTION_STATUS                        |

## 3. Relations (cardinalités)

```
CLIENT (1,n) ────── possède ────── (1,1) CONTRAT
CONTRAT (1,1) ────── génère ────── (0,n) SINISTRE
CONTRAT (1,1) ────── donne lieu à ── (0,n) PAIEMENT
```

- Un CLIENT possède 0 à n CONTRATs (un contrat appartient à un seul client).
- Un CONTRAT donne lieu à 0 à n SINISTREs et 0 à n PAIEMENTs.
- La clé `(source_system, source_id)` garantit qu'aucune collision d'identifiants entre les deux
  bases (ex. deux `CLIENT_ID = 42` provenant chacune d'un système différent) ne provoque de perte
  de données lors de la fusion.

## 4. Points de vigilance identifiés sur les schémas sources

- **Formats de date hétérogènes** : `AP_BIRTH_DATE` et `AP_INCIDENT_DATE` sont stockés en
  `VARCHAR` chez AssurePlus (`YYYY-MM-DD` et un format à 19 caractères probable `YYYY-MM-DD HH:MM:SS`)
  au lieu d'un type `DATE`/`DATETIME` natif → nécessite un parsing explicite et une validation
  (cf. `src/cleaning/data_cleaning.py`).
- **Nom éclaté vs concaténé** : `AB_NOM`/`AB_PRENOM` séparés côté AbAssurance, `AP_FULL_NAME`
  concaténé côté AssurePlus → nécessite une règle de split (avec gestion des particules et noms
  composés).
- **Prime annuelle vs mensuelle** : nécessite une normalisation d'unité avant toute comparaison
  ou agrégation cross-système.
- **Champs absents d'un côté** (`AB_NUM_FISCAL`, `AP_LOYALTY_SCORE`, `AP_FRAUD_SCORE`,
  `AP_TRANSACTION_STATUS`) : conservés en `nullable` dans le modèle cible plutôt que supprimés,
  pour ne pas perdre d'information exploitable par le futur modèle IA.

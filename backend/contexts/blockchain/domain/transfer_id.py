"""KRYP-25/37 — Dérivation déterministe de l'identifiant on-chain d'un transfert.

Le contrat Escrow (lock/release/refund) et AuditTrail.logCriticalEvent exigent un
``bytes32`` hexadécimal comme ``transferId``. L'UUID de transaction (avec tirets)
n'en est pas un — cette fonction le convertit en un hash déterministe valide,
avec exactement la même construction que les feuilles Merkle (KRYP-25, cf.
``escrow_lock_task`` / ``ProcessPayoutUseCase._queue_delivered_audit_hash``) :
``keccak256(transaction_id)``, préfixé ``0x``.

UNE SEULE fonction, appelée à CHAQUE point où un transferId on-chain est requis
(lock, release, refund, log_critical_event) : diverger produirait un transferId
différent entre le verrouillage et la libération/le remboursement, et le
contrat retournerait ``TransferNotLocked`` à tort.
"""
from web3 import Web3


def to_onchain_transfer_id(transaction_id: str) -> str:
    """Keccak256 de l'UUID de transaction → hex ``"0x..."`` (bytes32 valide)."""
    hex_str = Web3.keccak(text=transaction_id).hex()
    return hex_str if hex_str.startswith("0x") else "0x" + hex_str


def to_onchain_account_id(user_id: str) -> str:
    """KRYP-31 (partie 2/3) — même construction que ``to_onchain_transfer_id``,
    mais pour un événement lié à un COMPTE plutôt qu'à un transfert (gel de
    compte, génération de déclaration TRACFIN). ``AuditTrail.logCriticalEvent``
    n'attend qu'un ``bytes32`` opaque — son paramètre s'appelle ``transferId``
    par convention historique (KRYP-24) mais le contrat ne vérifie aucune
    relation avec un transfert réel (voir AuditTrail.sol) ; dériver un hash
    dédié à partir de l'UUID utilisateur évite toute ambiguïté avec un
    transferId réel dans les logs on-chain."""
    hex_str = Web3.keccak(text=f"account:{user_id}").hex()
    return hex_str if hex_str.startswith("0x") else "0x" + hex_str

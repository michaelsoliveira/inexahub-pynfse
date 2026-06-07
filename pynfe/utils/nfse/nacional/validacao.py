"""Validações auxiliares para NFS-e Nacional."""


def validar_cpf(cpf: str) -> bool:
    """Verifica dígitos verificadores do CPF (11 dígitos)."""
    digits = "".join(c for c in str(cpf or "") if c.isdigit())
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    for pos in range(9, 11):
        soma = sum(int(digits[i]) * (pos + 1 - i) for i in range(pos))
        digito = ((10 * soma) % 11) % 10
        if int(digits[pos]) != digito:
            return False
    return True

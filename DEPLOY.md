# Deploy em VPS

Requisitos: Ubuntu 24.04 com IP publico e portas TCP 22, 80 e 443 liberadas.

## DNS na Amen

Crie os registros abaixo, substituindo `IP_DA_VPS` pelo IPv4 publico da VM:

| Tipo | Nome | Valor |
| --- | --- | --- |
| A | `@` | `IP_DA_VPS` |
| A | `www` | `IP_DA_VPS` |

Remova outros registros A/AAAA conflitantes para `@` e `www`. Nao crie um
registro AAAA se a VPS nao possuir IPv6 configurado.

## Servidor

Instale Docker e o plugin Compose:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
newgrp docker
```

Baixe e inicie a aplicacao:

```bash
git clone https://github.com/joabzicg/Caiman.git
cd Caiman
docker compose up -d --build
docker compose ps
```

O Caddy solicita e renova automaticamente os certificados HTTPS quando os
registros DNS ja apontam para a VPS e as portas 80/443 estao acessiveis.

Enquanto o DNS nao propagar, o simulador tambem responde temporariamente em
`http://68.221.16.155`.

## Atualizacao

```bash
cd Caiman
git pull --ff-only
docker compose up -d --build
```

Para diagnostico:

```bash
docker compose logs --tail=100
```

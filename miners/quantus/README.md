# Quantus GPU pour HiveOS

Copier le binaire compilé dans :

```text
miners/quantus/quantus-miner
```

Puis :

```bash
chmod +x miners/quantus/*.sh miners/quantus/quantus-miner scripts/*.sh
./scripts/validate-miner.sh quantus
./scripts/package-miner.sh quantus
```

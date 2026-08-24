# Relatorio pessoal - implementacao dos drivers

Este resumo serve como apoio caso alguem pergunte o que foi feito, como foi
feito e qual foi a base tecnica usada para implementar os drivers do firmware.

## O que eu implementei

Foram implementados os drivers principais relacionados aos componentes que a
PCB realmente conecta ao STM32:

- `LSM6DSO`: IMU onboard, com acelerometro e giroscopio via I2C.
- `LIS2MDL`: magnetometro onboard via I2C.
- `LPS22HB`: barometro/sensor de pressao onboard via I2C.
- `battery`: leitura de `VBAT` e `VCHG` usando ADC e os divisores resistivos da
  PCB.
- `rf_comm`: comunicacao SPI com o radio `nRF24L01P`.
- `rgb_led`: controle da cadeia de LEDs SK6812.
- `esc`: geracao de PWM para os dois ESCs/thrusters.
- `bar30`: suporte ao sensor externo Bar30/MS5837 via I2C.

Tambem organizei a documentacao e criei um projeto Wokwi para validar os
protocolos antes da PCB fisica chegar.

## Como os drivers foram feitos

Primeiro eu relacionei cada driver com o esquematico da PCB. A ideia foi evitar
implementar driver para coisa que nao chega no MCU. Por exemplo, o magnetic
switch foi identificado como circuito de power control, nao como entrada de
firmware, entao ele nao precisa de driver.

Depois disso, cada driver foi feito seguindo a interface real do componente:

- Nos sensores I2C, o firmware le o registrador `WHO_AM_I`, configura os
  registradores principais e depois le os registradores de dados.
- No driver de bateria, o ADC mede a tensao no pino do STM32 e o firmware
  reconstrói a tensao real usando a razao dos resistores do divisor.
- No nRF24, o driver acessa registradores por SPI, configura canal, endereco,
  payload e expoe funcoes basicas para enviar/receber pacotes.
- No RGB, o driver gera a forma de onda serial esperada pelos SK6812 no pino
  `PC6`, passando pelo level shifter da PCB.
- No ESC, o driver inicializa o `TIM4` e gera pulsos de 50 Hz entre `1000 us` e
  `2000 us`.
- No Bar30, o driver segue o fluxo do MS5837: reset, leitura da PROM de
  calibracao, conversao de pressao/temperatura e calculo dos valores finais.

Um detalhe importante encontrado foi o `SPI1` configurado inicialmente como
`SPI_DATASIZE_4BIT`. Isso foi corrigido para `SPI_DATASIZE_8BIT`, porque o
nRF24 usa comandos e registradores de 8 bits.

## De onde veio a base tecnica

A implementacao foi baseada principalmente em:

- Datasheets dos sensores ST:
  - `LSM6DSO`
  - `LIS2MDL`
  - `LPS22HB`
- Datasheet/especificacao do `nRF24L01P` da Nordic.
- Datasheet/protocolo dos LEDs SK6812, compativel com a familia WS281x.
- Documentacao do Bar30/MS5837 usada pela Blue Robotics.
- Esquematico da PCB, para confirmar pinos, nets e componentes.
- Exemplos comuns de uso STM32 HAL para I2C, SPI, ADC, GPIO e timer PWM.
- API de custom chips do Wokwi para criar os sensores fake e testar os
  protocolos.

Os codigos nao foram simplesmente copiados prontos. A logica foi escrita para
encaixar na estrutura do firmware atual, usando os handles HAL e os pinos/nets
da nossa PCB.

## Como o Wokwi ajuda

O Wokwi nao simula a PCB completa nem usa o mesmo STM32F765 da placa real.
Mesmo assim, ele ajuda bastante porque valida o comportamento de protocolo:

- I2C dos sensores internos.
- I2C do Bar30 fake.
- SPI do nRF24 fake.
- Conversao de ADC para bateria/carga.
- Pulso PWM dos ESCs.
- Sinal serial dos LEDs RGB.

No projeto Wokwi, os custom chips responderam corretamente e o Serial Monitor
mostrou:

```text
Caiman Wokwi
LSM=0x6C OK
LIS=0x40 OK
LPS=0xB1 OK
B30 OK
RF OK
TX OK
```

Tambem foi usado o logic analyzer do Wokwi para confirmar atividade em I2C,
SPI, PWM e RGB data.

Link do projeto:

https://wokwi.com/projects/466385813995578369

## O que ainda depende da PCB real

Mesmo com os drivers implementados e o Wokwi validando os protocolos, ainda
precisa testar na placa real:

- Se os sensores aparecem no barramento I2C.
- Se os pull-ups, alimentacao e solda estao corretos.
- Se as leituras de ADC batem com o multimetro.
- Se o nRF24 responde no SPI real.
- Se o LED RGB recebe o sinal corretamente depois do level shifter.
- Se os pulsos dos ESCs estao corretos no osciloscopio/logic analyzer.
- Se o SD card e o logger funcionam de ponta a ponta.

Entao o estado atual e: firmware pronto para o primeiro bring-up, mas ainda nao
validado em hardware real.

## Como explicar em poucas palavras

Eu implementei os drivers dos componentes principais conectados ao STM32,
usando o esquematico para mapear os pinos e os datasheets para configurar cada
dispositivo. Depois montei um harness no Wokwi com chips customizados para
testar os protocolos antes da chegada da PCB. O firmware compila e esta pronto
para o primeiro teste de hardware, onde vamos validar alimentacao, barramentos,
leituras reais e sinais de saida.

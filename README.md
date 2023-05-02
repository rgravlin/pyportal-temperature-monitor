## PyPortal Temperature Monitor

The purpose of this project is to visually represent the a temperature based on localized sensors.  At this time I use it to quickly determine what gear I need for my dog and myself based on the temperature.

![negative fifteen degrees](_images/neg-fifteen.jpg)
![fifteen degrees](_images/fifteen.jpg)
![thirty five degrees](_images/thirty-five.jpg)
![fifty five degrees](_images/fifty-five.jpg)
![seventy five degrees](_images/seventy-five.jpg)
![ninety five degrees](_images/ninety-five.jpg)
![hundred and five degrees](_images/hundred-and-five.jpg)

I found weather apps and data to be fairly reliable but not accurate enough based on exactly where I live.

This would be considered a front-end component of another project which is the sensor and time series database project that I will eventually link here.

It uses a Feather S2 w/ BME280 sensor to capture the measurements below and publish them to a local time series database via a memory backed relay that replicates data both locally and to a free cloud service with lower retention for easy remote monitoring.

* Measurements:
  * Temperature F
  * Temperature C
  * Battery Voltage
  * Battery %
  * Humidity
  * Pressure
  * Git Version

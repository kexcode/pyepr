# pyepr
pyepr v.0.1.0 (Pure Python)

## Description:

An educational app for the EPR spectral simulations. The purpose of this app is to get user familiar with the EPR spectra calculations using [EasySpin](https://easyspin.org) package. All the basic routines are inspired by the [EasySpin](https://easyspin.org) package, but refactored to pure python and organized as REST API server. Future plans are to develop a web interface for the app. The app is using numpy and scipy for numerical calculations.
The Docker file is included for easy deployment. To run the app, use the command:

```bash

docker-compose up
```

## Features:

* EPR spectra calculation employs:
  *  [**pepper**](https://easyspin.org/easyspin/documentation/userguide_pepper.html) for a solid state EPR
  *  [**garlic**](https://easyspin.org/easyspin/documentation/userguide_garlic.html) for a liquid state EPR

* Orientation selection via specifying the [SampleFrame](https://easyspin.org/easyspin/documentation/frames.html) relative to the lab frame, the molecular frame is considered to be collinear with the sample frame for a simplicity.

* Energy level diagram is plotted only for selected orientation and supports all possible spin system parameters

* User friendly input format: easy to work with multiple nuclei systems, including equivalent nuclei. The parcing process to a suitable spin system is implemented.

* Loading of 1-dimentional EPR spectra (pulse and CW, but only .DSC files) is supported

* Saving parameters as a matlab structure is supported
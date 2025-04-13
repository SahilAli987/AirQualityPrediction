# Air Quality Index Prediction 🌍

## Overview
This repository contains a comprehensive Air Quality Index (AQI) prediction system that helps users determine air quality based on various pollutant parameters. The application provides both manual input prediction and real-time geolocation-based air quality monitoring.

## 🎯 Features
- **Manual Prediction**: Input pollutant levels manually to predict AQI
- **Geolocation-based Prediction**: Get real-time AQI predictions based on your current location
- **Interactive Visualization**: Explore relationships between different pollutants through charts and graphs
- **Health Recommendations**: Receive health advice based on the predicted AQI level
- **Model Performance Metrics**: View the model's accuracy and reliability

## 🔍 Key Parameters
The system considers the following pollutants for AQI prediction:
- PM2.5 (Fine particulate matter)
- NO2 (Nitrogen Dioxide)
- SO2 (Sulfur Dioxide)
- CO (Carbon Monoxide)
- O3 (Ozone)

## 🛠️ Technical Stack
- **Frontend**: Streamlit
- **Backend**: Python
- **ML Models**: 
  - XGBoost (Primary model)
  - Random Forest
  - Decision Tree
  - Linear Regression
  - Lasso Regression
  - Artificial Neural Network
- **APIs**: WAQI API for real-time air quality data

## 📊 Model Performance
- Model Accuracy: 89%
- Evaluation Metrics: R-squared score, MSE, RMSE
- Cross-validation implemented for robust performance

## 🔧 Installation & Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/SahilAli987/AirQualityPrediction.git
   ```
2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   streamlit run app.py
   ```

## 📚 Dependencies
- Python 3.5+
- streamlit
- pandas
- numpy
- scikit-learn
- xgboost
- requests
- matplotlib
- seaborn

## 📂 Project Structure
```
├── Data/
│   ├── city_hour.csv        # Raw dataset
│   └── final_data.csv       # Cleaned dataset
├── models/
│   ├── Linear_Regression.ipynb
│   ├── Decision_Tree.ipynb
│   ├── Random_Forest.ipynb
│   └── XGBoost.ipynb
├── app.py                   # Main application file
├── prediction.py           # Prediction logic
├── explore_page.py        # Data exploration page
└── requirements.txt       # Project dependencies
```

## 🌟 Recent Updates
- Added geolocation-based prediction feature
- Implemented health recommendations based on AQI levels
- Fixed feature name consistency across the application
- Enhanced UI with better visualization and user feedback
- Added model accuracy display

## 👥 Contributors
- MD SAHIL ALI
- ARYAN JAIN

## 📝 License
This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing
Contributions, issues, and feature requests are welcome! Feel free to check [issues page](https://github.com/SahilAli987/AirQualityPrediction/issues).

## 📧 Contact
For any queries or suggestions, please reach out to the contributors.

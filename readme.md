# My Finance

A web app to buy and sell stocks using virtual curency, and track your investment portfolio. The app uses the IEX API to fetch stock price data.
The user has access to the following features:

Main page
On the main page, you can see your current portfolio.

Quote
View current stock prices by looking up stocks by their symbol.

Buy
You can buy stocks by entering the stock symbol and number of shares. Before this, you may want to use the quote feature above to check the price.

Sell
Sell stocks by selecting the symbol from the list of owned stocks and number of shares you want to sell.

Add money
If you are running low on funds, you can deposit as much (fake) money as you like to buy some more stocks!

History
View transaction history including price, date and number of shares bought for any transaction you have made before. The data is saved in an SQLite database and saved on the server so history is maintained across sessions.

Change password
User can change their current password using this interface.

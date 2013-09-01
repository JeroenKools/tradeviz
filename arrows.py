'''
Created on 15 aug. 2013

@author: Jeroen
'''

from matplotlib.pyplot import figure, show

fig = figure(1, figsize=(7, 10))
ax = fig.add_subplot(111, autoscale_on=False, xlim=(0, 7), ylim=(0, 10))

for r in range(7):

    ax.annotate('',
                xy=(6 - .4 * r, 4 + r),
                xycoords='data', xytext=(1, .3 + r ** 1.15),
                size=20 + 5 * r,
                arrowprops=dict(arrowstyle="simple" ,
                                fc=(0.6, 0, 0), ec="none",
                                connectionstyle="arc3,rad=%f" % (r / 10.0)))

show()

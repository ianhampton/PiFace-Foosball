#!/usr/bin/env python

# Foosbot - Monitor sensors and increment goals
# Ian Hampton - October 2015
# Requires a Raspberry Pi with PiFace adapter

import pifacedigitalio as p
import time
import json
import urllib
import urllib2
from urllib2 import Request, urlopen
import slackweb

pfd = p.PiFaceDigital()

# Define the inputs/output pin number that the beam is connected to
RED_BEAM = 1
BLUE_BEAM = 0

# keeps track of the last state the beam was in
# used to know if a new event has occurred
redBeamStateWasBroken = False
blueBeamStateWasBroken = False

# Score tracker
redScore = 0
blueScore = 0

# Player names
defaultRedPlayer = "AnonymousRed"
defaultBluePlayer = "AnonymousBlue"
redPlayer = defaultRedPlayer
bluePlayer = defaultBluePlayer

# HipChat API key and room ID
V2TOKEN = 'xxx'
ROOMID = 000

# Slack API
SLACKID = 'xxx'

# Remote Domain
REMOTEDOMAIN = 'https://foosball.local'


def postToLeaderboard(player, winlose, points):
    url = REMOTEDOMAIN.'/leaderboard/f1_api.php'
    values = {'email_address': player, 'winlose': winlose, 'points': points}
    data = urllib.urlencode(values)
    req = urllib2.Request(url, data)
    response = urllib2.urlopen(req)
    the_page = response.read()
    return


def hipChatWin(winner, score, colour):
    # Send a winner notification to HipChat
    # API V2, send message to room:
    url = 'https://api.hipchat.com/v2/room/%d/notification' % ROOMID
    message = "<strong>{} WIN!</strong><br />Final score: {}".format(
        winner, score)
    headers = {
        "content-type": "application/json",
        "authorization": "Bearer %s" % V2TOKEN}
    datastr = json.dumps({
        'message': message,
        'color': colour,
        'message_format': 'html',
        'notify': False})
    request = Request(url, headers=headers, data=datastr)
    try:
        uo = urlopen(request)
        rawresponse = ''.join(uo)
        uo.close()
        assert uo.code == 204
    except:
        print 'Error connecting to HipChat API.'
    return


def slackWin(winner, score, icon):
    # Send a winner notification to Slack
    message = "{} WIN!\nFinal score: {}".format(winner, score)
    url = 'https://hooks.slack.com/services/{}'.format(SLACKID)
    try:
        slack = slackweb.Slack(url=url)
        slack.notify(text=message, channel="#team_solutions_emea",
                     username="FoosBot", icon_emoji=icon)
    except:
        print 'Error connecting to Slack API.'
    return


def updateRemoteScore(red, blue):
    # update the remote scoreboard score
    try:
        url = '{}score.php?' \
            'red={}&blue={}&key={}'.format(
                REMOTEDOMAIN, red, blue, V2TOKEN)
        uo = urlopen(url)
        uo.read()
        uo.close()
    except:
        print 'Error connecting to remote scoreboard.'
    return


def updateRemotePlayers(red, blue):
    # update the remote player names
    try:
        url = '{}player.php?' \
            'red={}&blue={}'.format(
                REMOTEDOMAIN, red, blue)
        uo = urlopen(url)
        print url
        uo.read()
        uo.close()
    except:
        print 'Error updating remote player service.'
    return


def incrementRemoteScore(red, blue):
    global redScore
    global blueScore

    # get current remote score
    try:
        req = urllib2.Request("{}score.json".format(REMOTEDOMAIN))
        opener = urllib2.build_opener()
        f = opener.open(req)
        remoteScore = json.loads(f.read())

        # increment and update
        redScore = int(remoteScore['red']) + red
        blueScore = int(remoteScore['blue']) + blue
        updateRemoteScore(redScore, blueScore)
    except:
        print 'Error incrementing remote score.'
    return


def getRemotePlayers():
    global redPlayer
    global bluePlayer

    # get remote players
    try:
        req = urllib2.Request("{}player.json".format(REMOTEDOMAIN))
        opener = urllib2.build_opener()
        f = opener.open(req)
        remotePlayer = json.loads(f.read())

        # set global vars
        redPlayer = remotePlayer['red']
        bluePlayer = remotePlayer['blue']
    except:
        print 'Error connecting to remote player service.'
    return


def updateAudienceStream(vid, event, team, redScore, blueScore):
    # post to AudienceStream
    ts = int(time.time())
    account = 'demo'
    profile = 'main'
    traceID = '000'
    base_url = 'http://datacloud.tealiumiq.com/vdata/i.gif'
    qs = '?tealium_vid={0}' \
        '&tealium_account={1}&tealium_profile={2}' \
        '&tealium_trace_id={3}&the_timestamp={4}&the_event={5}' \
        '&the_team={6}&red_score={7}&blue_score={8}' \
        '&app_name=digital%20velocity&email={0}&visitor_id={0}'.format(
            vid, account, profile,
            traceID, ts, event,
            team, redScore, blueScore)
    url = base_url + qs
    try:
        uo = urlopen(url)
        uo.read()
        uo.close()
        print url
        print "------------------------------"
    except:
        print 'Error connecting to AudienceStream.'
    return

# Reset remote scoreboard
updateRemoteScore(redScore, blueScore)

# Reset remote players
updateRemotePlayers(defaultRedPlayer, defaultBluePlayer)

# turn on IR LED emitters
pfd.output_pins[RED_BEAM].turn_on()
pfd.output_pins[BLUE_BEAM].turn_on()

# main  loop of the code
while (True):
    # read the current state of the beam
    redBeamStateIsBroken = (pfd.input_pins[RED_BEAM].value == 0)
    blueBeamStateIsBroken = (pfd.input_pins[BLUE_BEAM].value == 0)
    time.sleep(.01)

    # handle red beam
    # if the beam is broken, that is if the beam was not broken before but is
    # now
    if (not redBeamStateWasBroken and redBeamStateIsBroken):
        redBeamStateWasBroken = True
        # redScore = redScore + 1
        getRemotePlayers()
        incrementRemoteScore(1, 0)
        updateAudienceStream(redPlayer, 'score', 'red', redScore, blueScore)
        print "Red Goal (" + redPlayer + "): Reds {} -" \
              "Blues {}".format(redScore, blueScore)
        print "------------------------------"

        # Detect a winner
        if (redScore == 10):
            finalScore = "{} - {}".format(redScore, blueScore)
            print "REDS WIN! " + finalScore
            print "------------------------------"
            hipChatWin("REDS (" + redPlayer + ")", finalScore, "red")
            slackWin("REDS (" + redPlayer + ")", finalScore, ":red_circle:")
            updateAudienceStream(redPlayer, 'won', 'red', redScore, blueScore)
            updateAudienceStream(bluePlayer, 'lost', 'blue',
                                 redScore, blueScore)
            postToLeaderboard(redPlayer, 'won', redScore)
            postToLeaderboard(bluePlayer, 'lost', blueScore)
            redScore = 0
            blueScore = 0
            pfd.leds[6].turn_on()
            time.sleep(10)
            pfd.leds[6].turn_off()
            updateRemoteScore(redScore, blueScore)
            updateRemotePlayers(defaultRedPlayer, defaultBluePlayer)
        else:
            pfd.leds[6].turn_on()
            time.sleep(2)
            pfd.leds[6].turn_off()

    # this detects when the beam has become un-broken again.
    # That us when the beam was broken ad it is not broken any longer
    if (redBeamStateWasBroken and not redBeamStateIsBroken):
        redBeamStateWasBroken = False
        # print "red beam has been un-broken"

    # handle blue, with same structure as red
    if (not blueBeamStateWasBroken and blueBeamStateIsBroken):
        blueBeamStateWasBroken = True
        # blueScore = blueScore + 1
        getRemotePlayers()
        incrementRemoteScore(0, 1)
        updateAudienceStream(bluePlayer, 'score', 'blue', redScore, blueScore)
        print "Blue Goal (" + bluePlayer + "): Reds {} " \
              "- Blues {}".format(redScore, blueScore)
        print "------------------------------"

        # Detect a winner
        if (blueScore == 10):
            finalScore = "{} - {}".format(blueScore, redScore)
            print "BLUES WIN! " + finalScore
            print "------------------------------"
            hipChatWin("BLUES (" + bluePlayer + ")", finalScore, "purple")
            slackWin("BLUES (" + bluePlayer + ")",
                     finalScore, ":large_blue_circle:")
            updateAudienceStream(bluePlayer, 'won', 'blue',
                                 redScore, blueScore)
            updateAudienceStream(redPlayer, 'lost', 'red', redScore, blueScore)
            postToLeaderboard(redPlayer, 'lost', redScore)
            postToLeaderboard(bluePlayer, 'won', blueScore)
            redScore = 0
            blueScore = 0
            pfd.leds[7].turn_on()
            time.sleep(10)
            pfd.leds[7].turn_off()
            updateRemoteScore(redScore, blueScore)
            updateRemotePlayers(defaultRedPlayer, defaultBluePlayer)
        else:
            pfd.leds[7].turn_on()
            time.sleep(2)
            pfd.leds[7].turn_off()

    if (blueBeamStateWasBroken and not blueBeamStateIsBroken):
        blueBeamStateWasBroken = False
        # print "blue beam has been un-broken"

    # Reset switch
    if (pfd.switches[3].value != 0):
        redScore = 0
        blueScore = 0
        updateRemoteScore(redScore, blueScore)
        updateRemotePlayers(defaultRedPlayer, defaultBluePlayer)
        print "GAME RESET {} - {}".format(redScore, blueScore)
        print "------------------------------"
        time.sleep(2)

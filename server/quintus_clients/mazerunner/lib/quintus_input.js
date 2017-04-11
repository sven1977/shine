/*global Quintus:false, module:false */

/**
Quintus HTML5 Game Engine - Input Module

The code in `quintus_input.js` defines the `Quintus.Input` module, which
concerns itself with game-type (pretty anything besides touchscreen input)

@module Quintus.Input
*/


// returns the current game state (use x/y coordinates of the agent to calculate our tile-wise x/y)
function get_state(agent) {
	if (! agent) {
	    agent = AGENT;
    }
    // simple x,y state
	// OBSOLETE: use destX/Y istead of current x/y as this is the position that we definitely will be (after the stepWait interval)
    var x = parseInt((agent.p.x - 20) / 32);
    var y = parseInt((agent.p.y - 20) / 32);
	return [x == 8 ? 7 : x, y == 8 ? 7 : y];
}


// converts a state array (e.g. [1, 2]) into a python-tuple-string (e.g. "(1, 2)")
function state_to_str(s) {
	var ret = "("+s[0];
	if (s.length > 1) {
		for (var i = 1, l = s.length; i < l; ++i) {
			ret += ", "+s[i];
		}
	}
	return ret+")";
}


var _SCORE = 0; // total accumulated score
var _AVG_SCORE = 0; // average score per episode
var _NUM_EPISODES = 0;
function change_score(delta) {
	_SCORE += delta;
	// update scoreboard
	document.getElementById('displ_total_reward').innerHTML = _SCORE;
}


function episode_done() {
    _NUM_EPISODES++;
    _AVG_SCORE = _SCORE / _NUM_EPISODES;
	document.getElementById('displ_avg_reward').innerHTML = _AVG_SCORE.toFixed(2);
}


var quintusInput = function(Quintus) { 
"use strict";

/**
 * Quintus Input Module
 *
 * @class Quintus.Input
 */
Quintus.Input = function(Q) {
  /**
   * Provided key names mapped to key codes - add more names and key codes as necessary
   *
   * @for Quintus.Input
   * @property KEY_NAMES
   * @type Object
   * @static
   */
  var KEY_NAMES = Q.KEY_NAMES = {
    LEFT: 37, RIGHT: 39,
    UP: 38, DOWN: 40,

    ZERO : 48, ONE : 49, TWO : 50,
    THREE : 51, FOUR : 52, FIVE : 53,
    SIX : 54, SEVEN : 55, EIGHT : 56,
    NINE : 57,

    A : 65, B : 66, C : 67,
    D : 68, E : 69, F : 70,
    G : 71, H : 72, I : 73,
    J : 74, K : 75, L : 76,
    M : 77, N : 78, O : 79,
    P : 80, Q : 81, R : 82,
    S : 83, T : 84, U : 85,
    V : 86, W : 87, X : 88,
    Y : 89, Z : 90,

    ENTER: 13,
    ESC: 27,
    BACKSPACE : 8,
    TAB : 9,
    SHIFT : 16,
    CTRL : 17,
    ALT : 18,
    SPACE: 32,

    HOME : 36, END : 35,
    PGGUP : 33, PGDOWN : 34
  };

  var DEFAULT_KEYS = {
    LEFT: 'left', RIGHT: 'right',
    UP: 'up',     DOWN: 'down',
    SPACE: 'fire',
    Z: 'fire',
    X: 'action',
    ENTER: 'confirm',
    ESC: 'esc',
    P: 'P',
    S: 'S'
  };

  var DEFAULT_TOUCH_CONTROLS  = [ ['left','<' ],
                            ['right','>' ],
                            [],
                            ['action','b'],
                            ['fire', 'a' ]];

  // Clockwise from midnight (a la CSS)
  var DEFAULT_JOYPAD_INPUTS =  ['up', 'right', 'down', 'left'];

  /**
   * Current state of bound inputs
   *
   * @for Quintus.Input
   * @property Q.inputs
   * @type Object
   */
  Q.inputs = {};
  Q.joypad = {};
  Q.aiPolicyShutUp = 0; // last timestamp at which a AI policy shutup happened; after that, we wait for n seconds and can then start again acting via policy

  var hasTouch =  !!('ontouchstart' in window);


  /**
   *
   * Convert a canvas point to a stage point, x dimension
   *
   * @method Q.canvasToStageX
   * @for Quintus.Input
   * @param {Float} x
   * @param {Q.Stage} stage
   * @returns {Integer} x
   */
  Q.canvasToStageX = function(x,stage) {
    x = x / Q.cssWidth * Q.width;
    if(stage.viewport) {
      x /= stage.viewport.scale;
      x += stage.viewport.x;
    }

    return x;
  };

  /**
   *
   * Convert a canvas point to a stage point, y dimension
   *
   * @method Q.canvasToStageY
   * @param {Float} y
   * @param {Q.Stage} stage
   * @returns {Integer} y
   */
  Q.canvasToStageY = function(y,stage) {
      y = y / Q.cssWidth * Q.width;
      if(stage.viewport) {
        y /= stage.viewport.scale;
        y += stage.viewport.y;
      }

      return y;
  };



  /**
   *
   * Button and mouse input subsystem for Quintus.
   * An instance of this class is auto-created as {{#crossLink "Q.input"}}{{/crossLink}}
   *
   * @class Q.InputSystem
   * @extends Q.Evented
   * @for Quintus.Input
   */
  Q.InputSystem = Q.Evented.extend({
    keys: {},
    keypad: {},
    keyboardEnabled: false,
    touchEnabled: false,
    joypadEnabled: false,

    /**
     * Bind a key name or keycode to an action name (used by `keyboardControls`)
     *
     * @method bindKey
     * @for Q.InputSystem
     * @param {String or Integer} key - name or integer keycode for to bind
     * @param {String} name - name of action to bind to
     */
    bindKey: function(key,name) {
      Q.input.keys[KEY_NAMES[key] || key] = name;
    },

    /**
     * Enable keyboard controls by binding to events
     *
     * @for Q.InputSystem
     * @method enableKeyboard
     */
    enableKeyboard: function() {
      if(this.keyboardEnabled) { return false; }

      // Make selectable and remove an :focus outline
      Q.el.tabIndex = 0;
      Q.el.style.outline = 0;

      Q.el.addEventListener("keydown",function(e) {
        if(Q.input.keys[e.keyCode]) {
          var actionName = Q.input.keys[e.keyCode];
          Q.inputs[actionName] = true;
          Q.aiPolicyShutUp = Date.now(); // reset the time to now so we have to wait another n sec until we can act via AI policy again
          Q.input.trigger(actionName);
          Q.input.trigger('keydown',e.keyCode);
        }
        if(!e.ctrlKey && !e.metaKey) {
          e.preventDefault();
        }
      },false);

      Q.el.addEventListener("keyup",function(e) {
        if(Q.input.keys[e.keyCode]) {
          var actionName = Q.input.keys[e.keyCode];
          Q.inputs[actionName] = false;
          Q.aiPolicyShutUp = Date.now(); // reset the time to now so we have to wait another n sec until we can act via AI policy again
          Q.input.trigger(actionName + "Up");
          Q.input.trigger('keyup',e.keyCode);
        }
        e.preventDefault();
      },false);

      if(Q.options.autoFocus) {  Q.el.focus(); }
      this.keyboardEnabled = true;
    },


    /**
     * Convenience method to activate keyboard controls (call `bindKey` and `enableKeyboard` internally)
      *
     * @method keyboardControls
     * @for Q.InputSystem
     * @param {Object} [keys] - hash of key names or codes to actions
     */
    keyboardControls: function(keys) {
      keys = keys || DEFAULT_KEYS;
      Q._each(keys,function(name,key) {
       this.bindKey(key,name);
      },Q.input);
      this.enableKeyboard();
    },

    _containerOffset: function() {
      Q.input.offsetX = 0;
      Q.input.offsetY = 0;
      var el = Q.el;
      do {
        Q.input.offsetX += el.offsetLeft;
        Q.input.offsetY += el.offsetTop;
      } while(el = el.offsetParent);
    },

    touchLocation: function(touch) {
      var el = Q.el,
        posX = touch.offsetX,
        posY = touch.offsetY,
        touchX, touchY;

      if(Q._isUndefined(posX) || Q._isUndefined(posY)) {
        posX = touch.layerX;
        posY = touch.layerY;
      }

      if(Q._isUndefined(posX) || Q._isUndefined(posY)) {
        if(Q.input.offsetX === void 0) { Q.input._containerOffset(); }
        posX = touch.pageX - Q.input.offsetX;
        posY = touch.pageY - Q.input.offsetY;
      }

      touchX = Q.width * posX / Q.cssWidth;
      touchY = Q.height * posY / Q.cssHeight;


      return { x: touchX, y: touchY };
    },

    /**
     * Activate touch button controls - pass in an options hash to override
     *
     * Default Options:
     *
     *     {
     *        left: 0,
     *        gutter:10,
     *        controls: DEFAULT_TOUCH_CONTROLS,
     *        width: Q.width,
     *        bottom: Q.height
     *      }
     *
     * Default controls are left and right buttons, a space, and 'a' and 'b' buttons, as defined as an Array of Arrays below:
     *
     *      [ ['left','<' ],
     *        ['right','>' ],
     *        [],  // use an empty array as a spacer
     *        ['action','b'],
     *        ['fire', 'a' ]]
     *
     * @method touchControls
     * @for Q.InputSystem
     * @param {Object} [opts] - Options hash
     */
    touchControls: function(opts) {
      if(this.touchEnabled) { return false; }
      if(!hasTouch) { return false; }

      Q.input.keypad = opts = Q._extend({
        left: 0,
        gutter:10,
        controls: DEFAULT_TOUCH_CONTROLS,
        width: Q.width,
        bottom: Q.height,
        fullHeight: false
      },opts);

      opts.unit = (opts.width / opts.controls.length);
      opts.size = opts.unit - (opts.gutter * 2);

      function getKey(touch) {
        var pos = Q.input.touchLocation(touch),
            minY = opts.bottom - opts.unit;
        for(var i=0,len=opts.controls.length;i<len;i++) {
          var minX = i * opts.unit + opts.gutter;
          if(pos.x >= minX && pos.x <= (minX+opts.size) && (opts.fullHeight || (pos.y >= minY + opts.gutter && pos.y <= (minY+opts.unit - opts.gutter))))
          {
            return opts.controls[i][0];
          }
        }
      }

      function touchDispatch(event) {
        var wasOn = {},
            i, len, tch, key, actionName;

        // Reset all the actions bound to controls
        // but keep track of all the actions that were on
        for(i=0,len = opts.controls.length;i<len;i++) {
          actionName = opts.controls[i][0];
          if(Q.inputs[actionName]) { wasOn[actionName] = true; }
          Q.inputs[actionName] = false;
        }

        var touches = event.touches ? event.touches : [ event ];

        for(i=0,len=touches.length;i<len;i++) {
          tch = touches[i];
          key = getKey(tch);

          if(key) {
            // Mark this input as on
            Q.inputs[key] = true;

            // Either trigger a new action
            // or remove from wasOn list
            if(!wasOn[key]) {
              Q.input.trigger(key);
            } else {
              delete wasOn[key];
            }
          }
        }

        // Any remaining were on the last frame
        // and need to trigger an up action
        for(actionName in wasOn) {
          Q.input.trigger(actionName + "Up");
        }

        return null;
      }

      this.touchDispatchHandler = function(e) {
        touchDispatch(e);
        e.preventDefault();
      };


      Q._each(["touchstart","touchend","touchmove","touchcancel"],function(evt) {
        Q.el.addEventListener(evt,this.touchDispatchHandler);
      },this);

      this.touchEnabled = true;
    },

    /**
     * Turn off touch (button and joypad) controls and remove event listeners
     *
     * @method disableTouchControls
     * @for Q.InputSystem
     */
    disableTouchControls: function() {
      Q._each(["touchstart","touchend","touchmove","touchcancel"],function(evt) {
        Q.el.removeEventListener(evt,this.touchDispatchHandler);
      },this);

      Q.el.removeEventListener('touchstart',this.joypadStart);
      Q.el.removeEventListener('touchmove',this.joypadMove);
      Q.el.removeEventListener('touchend',this.joypadEnd);
      Q.el.removeEventListener('touchcancel',this.joypadEnd);
      this.touchEnabled = false;

      // clear existing inputs
      for(var input in Q.inputs) {
        Q.inputs[input] = false;
      }
    },

    /**
     * Activate joypad controls (i.e. 4-way touch controls)
     *
     * Lots of options, defaults are:
     *
     *     {
     *      size: 50,
     *      trigger: 20,
     *      center: 25,
     *      color: "#CCC",
     *      background: "#000",
     *      alpha: 0.5,
     *      zone: Q.width / 2,
     *      inputs: DEFAULT_JOYPAD_INPUTS
     *    }
     *
     *  Default joypad controls is an array that defines the inputs to bind to:
     *
     *       // Clockwise from midnight (a la CSS)
     *       var DEFAULT_JOYPAD_INPUTS =  [ 'up','right','down','left'];
     *
     * @method joypadControls
     * @for Q.InputSystem
     * @param {Object} [opts] -  joypad options
     */
   joypadControls: function(opts) {
      if(this.joypadEnabled) { return false; }
      if(!hasTouch) { return false; }

      var joypad = Q.joypad = Q._defaults(opts || {},{
        size: 50,
        trigger: 20,
        center: 25,
        color: "#CCC",
        background: "#000",
        alpha: 0.5,
        zone: Q.width / 2,
        joypadTouch: null,
        inputs: DEFAULT_JOYPAD_INPUTS,
        triggers: []
      });

      this.joypadStart = function(evt) {
        if(joypad.joypadTouch === null) {
          var touch = evt.changedTouches[0],
              loc = Q.input.touchLocation(touch);

          if(loc.x < joypad.zone) {
            joypad.joypadTouch = touch.identifier;
            joypad.centerX = loc.x;
            joypad.centerY = loc.y;
            joypad.x = null;
            joypad.y = null;
          }
        }
      };


      this.joypadMove = function(e) {
        if(joypad.joypadTouch !== null) {
          var evt = e;

          for(var i=0,len=evt.changedTouches.length;i<len;i++) {
            var touch = evt.changedTouches[i];

            if(touch.identifier === joypad.joypadTouch) {
              var loc = Q.input.touchLocation(touch),
                  dx = loc.x - joypad.centerX,
                  dy = loc.y - joypad.centerY,
                  dist = Math.sqrt(dx * dx + dy * dy),
                  overage = Math.max(1,dist / joypad.size),
                  ang =  Math.atan2(dx,dy);

              if(overage > 1) {
                dx /= overage;
                dy /= overage;
                dist /= overage;
              }

              var triggers = [
                dy < -joypad.trigger,
                dx > joypad.trigger,
                dy > joypad.trigger,
                dx < -joypad.trigger
              ];

              for(var k=0;k<triggers.length;k++) {
                var actionName = joypad.inputs[k];
                if(triggers[k]) {
                  Q.inputs[actionName] = true;

                  if(!joypad.triggers[k]) {
                    Q.input.trigger(actionName);
                  }
                } else {
                  Q.inputs[actionName] = false;
                  if(joypad.triggers[k]) {
                    Q.input.trigger(actionName + "Up");
                  }
                }
              }

              Q._extend(joypad, {
                dx: dx, dy: dy,
                x: joypad.centerX + dx,
                y: joypad.centerY + dy,
                dist: dist,
                ang: ang,
                triggers: triggers
              });

              break;
            }
          }
        }
        e.preventDefault();
      };

      this.joypadEnd = function(e) {
          var evt = e;

          if(joypad.joypadTouch !== null) {
            for(var i=0,len=evt.changedTouches.length;i<len;i++) {
            var touch = evt.changedTouches[i];
              if(touch.identifier === joypad.joypadTouch) {
                for(var k=0;k<joypad.triggers.length;k++) {
                  var actionName = joypad.inputs[k];
                  Q.inputs[actionName] = false;
                    if(joypad.triggers[k]) {
                        Q.input.trigger(actionName + "Up");
                    }
                }
                joypad.joypadTouch = null;
                break;
              }
            }
          }
          e.preventDefault();
      };

      Q.el.addEventListener("touchstart",this.joypadStart);
      Q.el.addEventListener("touchmove",this.joypadMove);
      Q.el.addEventListener("touchend",this.joypadEnd);
      Q.el.addEventListener("touchcancel",this.joypadEnd);

      this.joypadEnabled = true;
    },

    /**
     * Activate mouse controls - mouse controls don't trigger events, but just set `Q.inputs['mouseX']` & `Q.inputs['mouseY']` on each frame.
     *
     * Default options:
     *
     *     {
     *       stageNum: 0,
     *       mouseX: "mouseX",
     *       mouseY: "mouseY",
     *       cursor: "off"
     *     }
     *
     * @method mouseControls
     * @for Q.InputSystem
     * @param {Object} [options] - override default options
     */
    mouseControls: function(options) {
      options = options || {};

      var stageNum = options.stageNum || 0;
      var mouseInputX = options.mouseX || "mouseX";
      var mouseInputY = options.mouseY || "mouseY";
      var cursor = options.cursor || "off";

      var mouseMoveObj = {};

      if(cursor !== "on") {
          if(cursor === "off") {
              Q.el.style.cursor = 'none';
          }
          else {
              Q.el.style.cursor = cursor;
          }
      }

      Q.inputs[mouseInputX] = 0;
      Q.inputs[mouseInputY] = 0;

      Q._mouseMove = function(e) {
        e.preventDefault();
        var touch = e.touches ? e.touches[0] : e;
        var el = Q.el,
          rect = el.getBoundingClientRect(),
          style = window.getComputedStyle(el),
          posX = touch.clientX - rect.left - parseInt(style.paddingLeft, 10),
          posY = touch.clientY - rect.top  - parseInt(style.paddingTop, 10);

        var stage = Q.stage(stageNum);

        if(Q._isUndefined(posX) || Q._isUndefined(posY)) {
          posX = touch.offsetX;
          posY = touch.offsetY;
        }

        if(Q._isUndefined(posX) || Q._isUndefined(posY)) {
          posX = touch.layerX;
          posY = touch.layerY;
        }

        if(Q._isUndefined(posX) || Q._isUndefined(posY)) {
          if(Q.input.offsetX === void 0) { Q.input._containerOffset(); }
          posX = touch.pageX - Q.input.offsetX;
          posY = touch.pageY - Q.input.offsetY;
        }

        if(stage) {
          mouseMoveObj.x= Q.canvasToStageX(posX,stage);
          mouseMoveObj.y= Q.canvasToStageY(posY,stage);

          Q.inputs[mouseInputX] = mouseMoveObj.x;
          Q.inputs[mouseInputY] = mouseMoveObj.y;

          Q.input.trigger('mouseMove',mouseMoveObj);
        }
      };

      /**
       * Fired when the user scrolls the mouse wheel up or down
       * Anyone subscribing to the "mouseWheel" event will receive an event with one numeric parameter
       * indicating the scroll direction. -1 for down, 1 for up.
       * @private
       */
      Q._mouseWheel = function(e) {
        // http://www.sitepoint.com/html5-javascript-mouse-wheel/
        // cross-browser wheel delta
        e = window.event || e; // old IE support
        var delta = Math.max(-1, Math.min(1, (e.wheelDelta || -e.detail)));
        Q.input.trigger('mouseWheel', delta);
      };

      Q.el.addEventListener('mousemove',Q._mouseMove,true);
      Q.el.addEventListener('touchstart',Q._mouseMove,true);
      Q.el.addEventListener('touchmove',Q._mouseMove,true);
      Q.el.addEventListener('mousewheel',Q._mouseWheel,true);
      Q.el.addEventListener('DOMMouseScroll',Q._mouseWheel,true);
    },

    /**
     * Turn off mouse controls
     *
     * @method disableMouseControls
     * @for Q.InputSystem
     */
    disableMouseControls: function() {
      if(Q._mouseMove) {
        Q.el.removeEventListener("mousemove",Q._mouseMove, true);
        Q.el.removeEventListener("mousewheel",Q._mouseWheel, true);
        Q.el.removeEventListener("DOMMouseScroll",Q._mouseWheel, true);
        Q.el.style.cursor = 'inherit';
        Q._mouseMove = null;
      }
    },

    /**
     * Draw the touch buttons on the screen
     *
     * overload this to change how buttons are drawn
     *
     * @method drawButtons
     * @for Q.InputSystem
     */
    drawButtons: function() {
      var keypad = Q.input.keypad,
          ctx = Q.ctx;

      ctx.save();
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      for(var i=0;i<keypad.controls.length;i++) {
        var control = keypad.controls[i];

        if(control[0]) {
          ctx.font = "bold " + (keypad.size/2) + "px arial";
          var x = keypad.left + i * keypad.unit + keypad.gutter,
              y = keypad.bottom - keypad.unit,
              key = Q.inputs[control[0]];

          ctx.fillStyle = keypad.color || "#FFFFFF";
          ctx.globalAlpha = key ? 1.0 : 0.5;
          ctx.fillRect(x,y,keypad.size,keypad.size);

          ctx.fillStyle = keypad.text || "#000000";
          ctx.fillText(control[1],
                       x+keypad.size/2,
                       y+keypad.size/2);
        }
      }

      ctx.restore();
    },

    drawCircle: function(x,y,color,size) {
      var ctx = Q.ctx,
          joypad = Q.joypad;

      ctx.save();
      ctx.beginPath();
      ctx.globalAlpha=joypad.alpha;
      ctx.fillStyle = color;
      ctx.arc(x, y, size, 0, Math.PI*2, true);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    },



    /**
     * Draw the joypad on the screen
     *
     * overload this to change how joypad is drawn
     *
     * @method drawJoypad
     * @for Q.InputSystem
     */
    drawJoypad: function() {
      var joypad = Q.joypad;
      if(joypad.joypadTouch !== null) {
        Q.input.drawCircle(joypad.centerX,
                           joypad.centerY,
                           joypad.background,
                           joypad.size);

        if(joypad.x !== null) {
          Q.input.drawCircle(joypad.x,
                           joypad.y,
                           joypad.color,
                           joypad.center);
        }
      }

    },

    /**
     * Called each frame by the stage game loop to render any onscreen UI
     *
     * calls `drawJoypad` and `drawButtons` if enabled
     *
     * @method drawCanvas
     * @for Q.InputSystem
     */
    drawCanvas: function() {
      if(this.touchEnabled) {
        this.drawButtons();
      }

      if(this.joypadEnabled) {
        this.drawJoypad();
      }
    }


  });

  /**
   * Instance of the input subsytem that is actually used during gameplay
   *
   * @property Q.input
   * @for Quintus.Input
   * @type Q.InputSystem
   */
  Q.input = new Q.InputSystem();

  /**
   * Helper method to activate controls with default options
   *
   * @for Quintus.Input
   * @method Q.controls
   * @param {Boolean} joypad - enable 4-way joypad (true) or just left, right controls (false, undefined)
   */
  Q.controls = function(joypad) {
    Q.input.keyboardControls();

    if(joypad) {
      Q.input.touchControls({
        controls: [ [],[],[],['action','b'],['fire','a']]
      });
      Q.input.joypadControls();
    } else {
      Q.input.touchControls();
    }

    return Q;
  };


  /**
   * Platformer Control Component
   *
   * Adds 2D platformer controls onto a Sprite
   *
   * Platformer controls bind to left, and right and allow the player to jump.
   *
   * Adds the following properties to the entity to control speed and jumping:
   *
   *      {
   *        speed: 200,
   *        jumpSpeed: -300
   *      }
   *
   *
   * @class platformerControls
   * @for Quintus.Input
   */
  Q.component("platformerControls", {
    defaults: {
      speed: 200,
      jumpSpeed: -300,
      collisions: []
    },

    added: function() {
      var p = this.entity.p;

      Q._defaults(p,this.defaults);

      this.entity.on("step",this,"step");
      this.entity.on("bump.bottom",this,"landed");

      p.landed = 0;
      p.direction ='right';
    },

    landed: function(col) {
      var p = this.entity.p;
      p.landed = 1/5;
    },

    step: function(dt) {
      var p = this.entity.p;

      if(p.ignoreControls === undefined || !p.ignoreControls) {
        var collision = null;

        // Follow along the current slope, if possible.
        if(p.collisions !== undefined && p.collisions.length > 0 && (Q.inputs['left'] || Q.inputs['right'] || p.landed > 0)) {
          if(p.collisions.length === 1) {
            collision = p.collisions[0];
          } else {
            // If there's more than one possible slope, follow slope with negative Y normal
            collision = null;

            for(var i = 0; i < p.collisions.length; i++) {
              if(p.collisions[i].normalY < 0) {
                collision = p.collisions[i];
              }
            }
          }

          // Don't climb up walls.
          if(collision !== null && collision.normalY > -0.3 && collision.normalY < 0.3) {
            collision = null;
          }
        }

        if(Q.inputs['left']) {
          p.direction = 'left';
          if(collision && p.landed > 0) {
            p.vx = p.speed * collision.normalY;
            p.vy = -p.speed * collision.normalX;
          } else {
            p.vx = -p.speed;
          }
        } else if(Q.inputs['right']) {
          p.direction = 'right';
          if(collision && p.landed > 0) {
            p.vx = -p.speed * collision.normalY;
            p.vy = p.speed * collision.normalX;
          } else {
            p.vx = p.speed;
          }
        } else {
          p.vx = 0;
          if(collision && p.landed > 0) {
            p.vy = 0;
          }
        }

        if(p.landed > 0 && (Q.inputs['up'] || Q.inputs['action']) && !p.jumping) {
          p.vy = p.jumpSpeed;
          p.landed = -dt;
          p.jumping = true;
        } else if(Q.inputs['up'] || Q.inputs['action']) {
          this.entity.trigger('jump', this.entity);
          p.jumping = true;
        }

        if(p.jumping && !(Q.inputs['up'] || Q.inputs['action'])) {
          p.jumping = false;
          this.entity.trigger('jumped', this.entity);
          if(p.vy < p.jumpSpeed / 3) {
            p.vy = p.jumpSpeed / 3;
          }
        }
      }
      p.landed -= dt;
    }
  });



  // shine gridworld controls
  Q.component("shineGridWorldControls", {

    added: function() {
      var p = this.entity.p;
      // initialize this component with encapsulation
      p.shineControls = {};
      var shine = p.shineControls;

      shine.aiShutUpTimeout = 5; // sec after which the policy can take over again
      shine.aiFrameSkip = 4; // every how many frames should we AI act?
      shine.frameCount = 0; // some local frame counter (used for aiFrameSkip)
      //shine.lastAiAction = -1; // -1 == none; 0=no action; 1=up, 2=right, 3=down, 4=left
      shine.qTable = new QTable(5); // 5 actions
      shine.epsilon = 1.0; // start epsilon
      shine.epsilonMin = 0.0; // the minimum epsilon to use, ever
      shine.epsilonStep = 0.0004; // step by which we reduce epsilon each iteration
      shine.policy = new EpsilonGreedyPolicy(shine.epsilon, shine.qTable);
      shine.sarsBuffer = new SARSBuffer(50); // store max 50 items before pushing them down
      // gets called by the SARS buffer when "full"
      // - sends entire buffer to server and empties the buffer
      shine.sarsBuffer.register_full_handler(function(sars_buffer) {
            // only send if we have a connection and an algorithm,
	        // otherwise discard our buffer (can't do anything with the data)
            if (ALGORITHM_NAME != "" && CONNECTION == true) {
                requestAddExperience(ALGORITHM_NAME, sars_buffer.buffer);
                console.log("Sending "+sars_buffer.buffer.length+" sars items to server.");
            }
            sars_buffer.empty();
      });
      shine.sars = [get_state(this.entity)]; // the current sars tuple to complete (before we can add it to our buffer)
      shine.goalState = [7, 4]; // x,y of the goal state
      //shine.isTerminated = false; // did we just terminate an episode?
      shine.a = 0;

      if(!p.stepDistance) { p.stepDistance = 32; }
      if(!p.stepDelay) { p.stepDelay = 0.2; }

      p.xMin = p.yMin = 10;
      p.xMax = p.yMax = 280;
      p.stepWait = 0;
      p.destX = p.x
      p.destY = p.y

      // component's step method is called AFTER sprite's (entity's) step method
      this.entity.on("step", this, "step");
      this.entity.on("hit", this, "collision");
    },

    collision: function(col) {
      var p = this.entity.p;
      var shine = p.shineControls;

      // we are done with this episode
      if(col.obj.isA("Tower")) {
          //Q.stageScene("endGame", 1, { label: "You Won!" });
          p.x = p.destX = p.startX;//destroy();
          p.y = p.destY = p.startY;
          // TODO: add terminal state signal here (e.g. (s=6,4 should not transition into 0,0, but into some terminal state (e.g. -1,-1), with value 0))
          this.process_sars(shine.a, 100, get_state());
          p.stepping = false;
          episode_done();
      }
      // we collided with a wall
      else if(p.stepping) {
        p.stepping = false;
        p.x = p.destX = p.origX;
        p.y = p.destY = p.origY;
        this.process_sars(shine.a, -1, get_state());
      }
    },

    process_sars: function(a, r, s_){
        change_score(r);
        var shine = this.entity.p.shineControls;
	    if (shine.sars.length == 1) {
            //console.log("finishing old sars: s="+shine.sars[0]+" a="+a+" r="+LAST_REWARD+" s'="+s_);
	    	shine.sars.push(a, r, s_);
            shine.sarsBuffer.add_item(shine.sars);
		}
	    else {
	        console.error("ERROR: sars tuple is not of length 1!");
        }

		// start a new sars tuple
        //console.log("starting new sars: s="+s_);
        shine.sars = [s_];
    },
    step: function(dt) {
      var p = this.entity.p;
      var shine = p.shineControls;
      shine.frameCount++; // increase frameCounter

      // are we AI controlled or keyboard controlled?
      var doFrame = (shine.frameCount % shine.aiFrameSkip == 0);
      var doAI = (Q.aiPolicyShutUp + (shine.aiShutUpTimeout * 1000) < Date.now());

      // still within stepWait time: smooth stepping part
      p.stepWait -= dt;
      if(p.stepping) {
        p.x += p.diffX * dt / p.stepDelay;
        p.y += p.diffY * dt / p.stepDelay;
      }
      if(p.stepWait > 0) { return; }
      // end: smooth stepping part

      // outside of stepWait time: finish the step in one single leap (right now)
      if(p.stepping) {
        p.x = p.destX;
        p.y = p.destY;
        // signal: not in smooth stepping part anymore (step done)
        p.stepping = false;
        // process this SARS tuple
        this.process_sars(shine.a, 0, get_state());
      }

      if (doAI) {
          p.stepDelay = 0.07; // very fast AI
          var s = get_state(); // get state right now (just to pull action from policy)
          shine.epsilon -= shine.epsilonStep;
          if (shine.epsilon < shine.epsilonMin) {
            shine.epsilon = shine.epsilonMin;
          }
          document.getElementById("displ_epsilon").innerHTML = shine.epsilon.toFixed(4);
          shine.a = shine.policy.get_a(state_to_str(s), shine.epsilon);
      }
      // manual
      else {
          p.stepDelay = 0.2;

          shine.a = 0;
          // arrow keys pressed
          if (Q.inputs['left']) {
              shine.a = 4;
          }
          else if (Q.inputs['right']) {
              shine.a = 2;
          }
          else if (Q.inputs['up']) {
              shine.a = 1;
          }
          else if (Q.inputs['down']) {
              shine.a = 3;
          }
      }

      // special case: do nothing -> process sars right here as we will not do any stepping
      if (shine.a == 0) {
          this.process_sars(shine.a, 0, get_state());
      }
      else {
          // determine diffX/Y
          p.diffX = 0;
          p.diffY = 0;
          if (shine.a == 1) {
              p.diffY = -p.stepDistance;
          }
          else if (shine.a == 2) {
              p.diffX = p.stepDistance;
          }
          else if (shine.a == 3) {
              p.diffY = p.stepDistance;
          }
          else if (shine.a == 4) {
              p.diffX = -p.stepDistance;
          }

          // set x/y directly to new position (+stepDistance)
          if (p.diffY || p.diffX) {
              p.stepping = true; // we start stepping ...
              //shine.currentStep = shine.frameCount;
              p.origX = p.x;
              p.origY = p.y;
              p.destX = p.x + p.diffX;
              p.destY = p.y + p.diffY;

              //console.log("y="+p.destY);

              // put some boundaries here so the agent cannot leave the maze
              if (p.destX < p.xMin) p.destX = p.xMin;
              if (p.destX > p.xMax) p.destX = p.xMax;
              if (p.destY < p.yMin) p.destY = p.yMin;
              if (p.destY > p.yMax) p.destY = p.yMax;

              p.stepWait = p.stepDelay;
          }
      }
    }

  });



  /**
   * Step Controls component
   *
   * Adds Step (square grid based) 4-ways controls onto a Sprite
   *
   * Adds the following properties to the entity:
   *
   *      {
   *        stepDistance: 32, // should be tile size
   *        stepDelay: 0.2  // seconds to delay before next step
   *      }
   *
   *
   * @class stepControls
   * @for Quintus.Input
   */
  Q.component("stepControls", {

    added: function() {
      var p = this.entity.p;

      if(!p.stepDistance) { p.stepDistance = 32; }
      if(!p.stepDelay) { p.stepDelay = 0.2; }

      p.stepWait = 0;
      p.destX = p.x
      p.destY = p.y

      // component's step method is called AFTER sprite's (entity's) step method
      this.entity.on("step",this,"step");
      this.entity.on("hit", this,"collision");
    },

    collision: function(col) {
      var p = this.entity.p;

      if(p.stepping) {
        p.stepping = false;
        p.x = p.origX;
        p.y = p.origY;
      }

    },

    step: function(dt) {
      var p = this.entity.p,
          moved = false;
      var shine = this.entity.p.shine;

      // still within stepWait time: smooth stepping part
      p.stepWait -= dt;
      if(p.stepping) {
        p.x += p.diffX * dt / p.stepDelay;
        p.y += p.diffY * dt / p.stepDelay;
      }
      if(p.stepWait > 0) { return; }
      // end: smooth stepping part

      // outside of stepWait time: finish the step in one single leap (right now)
      if(p.stepping) {
        p.x = p.destX;
        p.y = p.destY;
        // signal: not in smooth stepping part anymore (step done)
        p.stepping = false;
        shine.a = 0;
      }

      p.diffX = 0;
      p.diffY = 0;

      // arrow keys pressed
      if(Q.inputs['left']) {
        p.diffX = -p.stepDistance;
        shine.a = 4;
      }
      else if(Q.inputs['right']) {
         p.diffX = p.stepDistance;
         shine.a = 2;
      }
      else if(Q.inputs['up']) {
        p.diffY = -p.stepDistance;
        shine.a = 1;
      }
      else if(Q.inputs['down']) {
        p.diffY = p.stepDistance;
        shine.a = 3;
      }

      if (p.diffY || p.diffX) {
		p.stepping = true; // we start stepping ...
        shine.currentStep = shine.frameCount;
        p.origX = p.x;
        p.origY = p.y;
        p.destX = p.x + p.diffX;
        p.destY = p.y + p.diffY;
        p.stepWait = p.stepDelay;
      }
    }

  });




};


};

if(typeof Quintus === 'undefined') {
  module.exports = quintusInput;
} else {
  quintusInput(Quintus);
}

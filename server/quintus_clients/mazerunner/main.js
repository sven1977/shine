
window.addEventListener("load", function(e) {


// initialize the Quintus Game Engine
var Q = window.Q = Quintus();

var debugLevel = 0;
//debugLevel |= Q._DEBUG_LOG_COLLISIONS; Q._DEBUG_LOG_COLLISIONS_AS = 0;//"Erik";
//debugLevel |= (Q._DEBUG_LOG_COLLISIONS | Q._DEBUG_CLEAR_CONSOLE); Q._DEBUG_LOG_COLLISIONS_AS = 0;//"Erik";
//debugLevel |= Q._DEBUG_LOG_ANIMATIONS;
//debugLevel |= (Q._DEBUG_RENDER_SPRITES_PINK | Q._DEBUG_RENDER_COLLISION_LAYER);
//debugLevel |= Q._DEBUG_RENDER_SPRITES_FILL;
//debugLevel |= Q._DEBUG_RENDER_OFTEN;
//debugLevel |= (Q._DEBUG_RENDER_OFTEN | Q._DEBUG_RENDER_OFTEN_AND_LOCATE);


Q.include("Sprites, Scenes, Input, 2D, Anim, Touch, UI, Audio")
	.setup({
		//width: Math.min(document.documentElement.clientWidth, 640),
		//height: Math.min(document.documentElement.clientHeight, 480),
		development: true,
		maximize: false, // "touch"
		//maxWidth: 300,
		//maxHeight: 200,
		debugLevel: debugLevel,
	}).enableSound().controls();

Q.input.mouseControls({cursor: "on"});
//Q.input.keyboardControls();

SOCKET = 0;
SEQ_NUM = 0; // our own seqNum
SEQ_NUM_EXPECTED = 0; // expected seqNum by server
BUTTON_LIST = ['btt_disconnect', 'btt_list_projects', 'btt_new_project', 'btt_get_project', 'btt_set_project', 'btt_new_world', 'btt_new_algorithm', 'btt_run_algorithm'];
CODE_ID = 0; // int: client-unique code Id

var _TILE_SIZE = 16,
    _PLAYER_SIZE = 16;
    Q._EMPTY_OBJ = {}; // a read-only(!) empty object to reuse (to avoid excessive garbage collection)


_SCORE = 0;
change_score(0);
function change_score(delta) {
	_SCORE += delta;
	// update scoreboard
	document.getElementById('debugtxt').innerHTML = "Score: "+_SCORE;
}

// translates an action number into a keyboard event
function action_to_event(a) {
	if (a <= 0) {
        console.warn("WARNING: action a ("+a+") is <= 0!");
    }
    return a == 1 ? 'up' : a == 2 ? 'right' : a == 3 ? 'down' : a == 4 ? 'left' : 'no-action';
}

// returns the current game state
function get_state() {
    return []; TODO
}


// -------------------------------------
// GAME CONTROLS (components)
// -------------------------------------

// -------------------------------------
// MAIN CODE
// -------------------------------------

// the player sprite
Q.Sprite.extend("Player", {
	init: function(p) {
		this._super(p, { sheet: "player", gravity: 0 });
		this.add('2d, stepControls');

		this.on("walkonestep");
		this.aiShutUpTimeout = 10; // sec after which the policy can take over again
		this.aiFrameSkip = 4; // every how many frame should we act?
		this.frameCount = 0; // some local frame counter (used for aiFrameSkip)
		this.lastAiAction = -1; // -1 == none; 0=no action; 1=up, 2=right, 3=down, 4=left
		this.qTable = QTable(5); // 5 actions
		this.epsilon = 0.1;
		this.epsilonMin = 0.01;
		this.epsilonStep = 0.01;
		this.policy = EpsilonGreedyPolicy(this.epsilon, this.qTable);

		this.on("hit.sprite", function(collision) {
			if(collision.obj.isA("Tower")) {
				change_score(20);
				//Q.stageScene("endGame", 1, { label: "You Won!" }); 
				this.p.x = this.p.startX;//destroy();
				this.p.y = this.p.startY;
			}
		});
	},
	// put the AI policy here
	step: function(dt) {
		// long time no human interaction -> we can do AI
		if (Q.aiPolicyShutUp + 10000 < Date.now()) {
			// are we in an n-th frame? (act only every n frames)
			if (this.frameCount % this.aiFrameSkip == 0) {
				// anneal epsilon
				this.epsilon -= this.epsilonStep;
				if (this.epsilon < this.epsilonMin) {
					this.epsilon = this.epsilonMin;
				}
				// get the action
				var a = this.policy.get_a(get_state());
				// set Q.inputs
				var direction = action_to_event(this.lastAiAction)

				// if we are here the first time after a shutup, we have to set all events to false
				if (this.lastAiAction == -1) {
					for (var dir in ['up', 'down', 'left', 'right']) {
						Q.inputs[event] = false;
                    }
				}
				// otherwise, only set the this.lastAiAction to false
				else if (this.lastAiAction > 0) {
					Q.inputs[action_to_event(this.lastAiAction)] = false;
				}

				// remember last action for next time
				this.lastAiAction = a;
				// and set the correct direction in the inputs
				if (a > 0) {
					Q.inputs[direction] = true;
				}
			}
		}
		// first time we run step with being shutUp
		else if (this.lastAiAction >= 0) {
			// erase last action (if there was any)
			if (this.lastAiAction != 0) {
				Q.inputs[action_to_event(this.lastAiAction)] = false;
            }
			this.lastAiAction = -1; // reset our lastAction marker
		}
	},
	walkonestep: function(e) {
		change_score(-1);
		return e;
	}
});


// the tower sprite
// Sprites can be simple, the Tower sprite just sets a custom sprite sheet
Q.Sprite.extend("Tower", {
  init: function(p) {
    this._super(p, { sheet: 'tower' });
  }
});


// the level
// create a scene
Q.scene("level1", function(stage) {
	stage.collisionLayer(new Q.TileLayer({ dataAsset: 'level.json', sheet: 'tiles' }));
	var player = stage.insert(new Q.Player({ startX: 64, x: 64, startY: 32, y: 32 }));

	stage.add("viewport");//.follow(player);

	//stage.insert(new Q.Enemy({ x: 700, y: 0 }));
	//stage.insert(new Q.Enemy({ x: 800, y: 0 }));
	stage.insert(new Q.Tower({ x: 272, y: 178 }));
});

// end of game scene
Q.scene('endGame', function(stage) {
	var box = stage.insert(new Q.UI.Container({
		x: Q.width/2, y: Q.height/2, fill: "rgba(0,0,0,0.5)"
	}));
  
	var button = box.insert(new Q.UI.Button({ x: 0, y: 0, fill: "#CCCCCC", label: "Play Again" }))         
	var label = box.insert(new Q.UI.Text({x:10, y: -10 - button.p.h, label: stage.options.label }));
	button.on("click", function() {
		Q.clearStages();
		Q.stageScene('level1');
	});
	box.fit(20);
});



// start the game (load assets, stage the scene)
Q.load("sprites.png, sprites.json, level.json, tiles.png", function() {
	Q.sheet("tiles", "tiles.png", { tilew: 32, tileh: 32 });
	Q.compileSheets("sprites.png", "sprites.json");
	Q.stageScene("level1");
});


}); // end: addEventListener("load" ...



// -------------------------------------
// standalone functions
// -------------------------------------

// rerenders the entire canvas for debugging purposes
// - can be called at any time during a sprite's step method
function renderAllForDebug(Q, sprite) {
	sprite.refreshMatrix();
	Q._generateCollisionPoints(sprite);

	if(Q.ctx) { Q.clear(); }

	for(i =0,len=Q.stages.length;i<len;i++) {
		Q.activeStage = i;
		stage = Q.stage();
		if(stage) {
			stage.render(Q.ctx);
		}
	}
	Q.activeStage = 0;//sprite.stage; //??? stage number, not object
	if(Q.input && Q.ctx) { Q.input.drawCanvas(Q.ctx); }
}





// -------------------------------
// for shine prototype/demo
// -------------------------------

function onMessage(event) {
	json = event.data;
	jsonObj = JSON.parse(json);
	if (jsonObj.seqNum != SEQ_NUM_EXPECTED) {
		console.log("ERROR: seq num from server ("+jsonObj.seqNum+") incorrect! Expected "+SEQ_NUM_EXPECTED+"!")
	}
	++SEQ_NUM_EXPECTED;
	console.log("Received from server: "+json);
	
	if (jsonObj.msgType == "request") {
		if (jsonObj.request == "hello") {
			responseHello();
		}
	}
	else if (jsonObj.msgType == "response") {
		if (jsonObj.errMsg) {
			alert(jsonObj.errMsg);
		}
	}
	else if (jsonObj.msgType == "notify") {
		if (jsonObj.errMsg) {
			alert(jsonObj.errMsg);
		}
		else if (jsonObj.notify == "welcome") {
			alert("Successfully logged in!");
		}
	}
}

function resetButtons() {
	SEQ_NUM = 0;
	SEQ_NUM_EXPECTED = 0;
	document.getElementById('btt_connect').disabled = false;
	for (id of BUTTON_LIST) {
		document.getElementById(id).disabled = true;
	}
}


function connect() {
	console.log("Connecting to pyrate server");
	SOCKET = new WebSocket("ws://localhost:2017");
	SOCKET.onmessage = onMessage;
	document.getElementById('btt_connect').disabled = true;
	for (id of BUTTON_LIST) {
		document.getElementById(id).disabled = false;
	}

	SOCKET.onclose = function(event) {
		console.log("Connection to server was closed!");
		resetButtons();
	};
}

function responseHello() {
	json = {response : "hello", userName: "sven", password: "123456", "protocolVersion" : 1};
	sendJson(json);
}

function sendJson(msg) {
	var msgType = msg.request ? "request" : msg.response ? "response" : "notify";
	var seqNum = SEQ_NUM++;
	var json = msg;
	// add some automatic standard fields
	json.origin = "client";
	json.msgType = msgType;
	json.seqNum = seqNum;
	SOCKET.send(JSON.stringify(json));
}

function requestListProjects() {
	sendJson({request:"list projects"});
}

function requestListManagers() {
	sendJson({request:"list managers"});
}


function requestGetProject() {
	sendJson({request:"get project"});
}

function requestNewProject() {
	var projName = document.getElementById('txt_new_project').value;
	sendJson({request: "new project", projectName: projName})
}

function requestSetProject() {
	var projName = document.getElementById('txt_set_project').value;
	sendJson({request:"set project", projectName: projName});
}

//function requestExecuteCode() {
//	code = document.getElementById('txt_code').value;
//	sendJson({request:"execute code", codeId: CODE_ID++, "code": code});
//}

function requestNewWorld() {
	var worldName = document.getElementById('txt_new_world').value;
	sendJson({request: "new world", worldName: worldName})
}

function requestNewAlgorithm() {
	var algoName = document.getElementById('txt_new_algorithm').value;
	sendJson({request: "new algorithm", algorithmName: algoName})
}

function requestRunAlgorithm() {
	var algoName = document.getElementById('txt_run_algorithm').value;
	var worldName = document.getElementById('txt_run_on_world').value;
	sendJson({request: "run algorithm", algorithmName: algoName, worldName: worldName})
}


// sends a batch of experience tuples to the server for storage in the ReplayMemory
function requestAddExperience(world, buffer) {
	sendJson({request: "add experience", "worldName": world, "experienceList": buffer})
	//buffer.length = 0; // clear out buffer after sending
}

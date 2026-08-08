import { Emotion, AssistantState } from '../models/visionState';

export class Particle {
  constructor({ angle, radius, size, alpha, speed, life }) {
    this.angle = angle;
    this.radius = radius;
    this.size = size;
    this.alpha = alpha;
    this.speed = speed;
    this.life = life;
    this.trail = [];
  }
}

export class ExprTargets {
  constructor({
    browRaise = 0.15,
    browTilt = 0,
    eyeOpen = 0.85,
    lowerLid = 0.05,
    pupil = 0.5,
    mouthCurve = 0.1,
    mouthOpen = 0,
    heart = 0,
    blush = 0,
  } = {}) {
    this.browRaise = browRaise;
    this.browTilt = browTilt;
    this.eyeOpen = eyeOpen;
    this.lowerLid = lowerLid;
    this.pupil = pupil;
    this.mouthCurve = mouthCurve;
    this.mouthOpen = mouthOpen;
    this.heart = heart;
    this.blush = blush;
  }
}

export function exprFor(emotion) {
  switch (emotion) {
    case Emotion.HAPPY:
      return new ExprTargets({
        browRaise: 0.45,
        browTilt: 0.1,
        eyeOpen: 0.72,
        lowerLid: 0.55,
        pupil: 0.6,
        mouthCurve: 0.85,
        mouthOpen: 0.08,
        blush: 0.3,
      });
    case Emotion.SAD:
      return new ExprTargets({
        browRaise: -0.1,
        browTilt: 0.8,
        eyeOpen: 0.7,
        lowerLid: 0.15,
        pupil: 0.55,
        mouthCurve: -0.6,
      });
    case Emotion.THINKING:
      return new ExprTargets({
        browRaise: 0.2,
        browTilt: -0.2,
        eyeOpen: 0.66,
        lowerLid: 0.12,
        pupil: 0.45,
        mouthCurve: -0.05,
      });
    case Emotion.ALERT:
    case Emotion.ANGRY:
      return new ExprTargets({
        browRaise: -0.35,
        browTilt: -0.85,
        eyeOpen: 1.0,
        lowerLid: 0.2,
        pupil: 0.32,
        mouthCurve: -0.35,
        mouthOpen: 0.12,
      });
    case Emotion.SURPRISED:
      return new ExprTargets({
        browRaise: 1.0,
        browTilt: 0.1,
        eyeOpen: 1.0,
        lowerLid: 0.0,
        pupil: 0.85,
        mouthCurve: 0.0,
        mouthOpen: 0.6,
      });
    case Emotion.LOVE:
      return new ExprTargets({
        browRaise: 0.4,
        browTilt: 0.2,
        eyeOpen: 0.62,
        lowerLid: 0.5,
        pupil: 0.75,
        mouthCurve: 0.7,
        mouthOpen: 0.06,
        heart: 1.0,
        blush: 0.65,
      });
    case Emotion.CURIOUS:
      return new ExprTargets({
        browRaise: 0.55,
        browTilt: -0.1,
        eyeOpen: 0.92,
        lowerLid: 0.05,
        pupil: 0.62,
        mouthCurve: 0.2,
        mouthOpen: 0.05,
      });
    case Emotion.SLEEPY:
      return new ExprTargets({
        browRaise: -0.05,
        browTilt: 0.15,
        eyeOpen: 0.3,
        lowerLid: 0.25,
        pupil: 0.55,
        mouthCurve: 0.0,
        mouthOpen: 0.05,
      });
    case Emotion.WINK:
    case Emotion.NEUTRAL:
    default:
      return new ExprTargets();
  }
}

export class FaceParams {
  constructor(data = {}) {
    this.primary = data.primary || '#5082B4';
    this.secondary = data.secondary || '#285078';
    this.state = data.state || AssistantState.IDLE;

    this.browRaise = data.browRaise ?? 0.15;
    this.browTilt = data.browTilt ?? 0;
    this.eyeOpen = data.eyeOpen ?? 0.85;
    this.lowerLid = data.lowerLid ?? 0.05;
    this.pupilDilate = data.pupilDilate ?? 0.5;
    this.mouthCurve = data.mouthCurve ?? 0.1;
    this.mouthOpenBase = data.mouthOpenBase ?? 0;
    this.heart = data.heart ?? 0;
    this.blush = data.blush ?? 0;

    this.blink = data.blink ?? 0;
    this.wink = data.wink ?? 0;
    this.pupilX = data.pupilX ?? 0;
    this.pupilY = data.pupilY ?? 0;

    this.micLevel = data.micLevel ?? 0;
    this.aiLevel = data.aiLevel ?? 0;
    this.mouth = data.mouth ?? 0;

    this.headTurn = data.headTurn ?? 0;
    this.headTilt = data.headTilt ?? 0;

    this.breath = data.breath ?? 0;
    this.t = data.t ?? 0;
    this.floatY = data.floatY ?? 0;
    this.hudA = data.hudA ?? 0;
    this.hudB = data.hudB ?? 0;
    this.core = data.core ?? 0;
    this.rippleRadius = data.rippleRadius ?? 0;
    this.rippleAlpha = data.rippleAlpha ?? 0;
    this.micMuted = data.micMuted ?? false;

    this.particles = data.particles || [];
    this.wave = data.wave || new Array(56).fill(0);
  }
}

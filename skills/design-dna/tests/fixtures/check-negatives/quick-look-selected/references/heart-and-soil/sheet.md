# Reference sheet: https://www.heartandsoilflowers.com/

Studied 2026-09-07T21:55:39.109Z by study_reference.mjs (schema 2, QUICK LOOK: home only, for choosing, not for copying; run the full study before selecting). Every number below was read from the live site; nothing here was typed by hand.

## Ground and ink
Visible ground, sampled (elementFromPoint on a 16x10 grid at 8 scroll positions; media is its own bucket; shares sum to 1):
- ground rgb(237, 235, 223): 21.2% of sampled points
- ground rgb(173, 173, 196): 6.8% of sampled points
- ground rgb(63, 82, 26): 4.6% of sampled points
- ground rgb(220, 217, 200): 3.7% of sampled points
- ground rgb(214, 201, 181): 0.6% of sampled points
- media (photographs, video, canvas, background images): 63.0% of sampled points
- narrow, sampled: rgb(237, 235, 223) 26%; rgb(173, 159, 55) 10%; rgb(173, 173, 196) 7%; media 48%
Stacked-rectangle estimate (viewport-clipped element boxes summed; overlapping layers double count, so this can exceed 100% and is NOT visible area):
- rgb(237, 235, 223): 38.9% of summed boxes across 4 elements
- rgb(46, 59, 20): 21.4% of summed boxes across 3 elements
- rgb(214, 201, 181): 14.2% of summed boxes across 1 elements
- rgb(173, 159, 55): 13.4% of summed boxes across 1 elements
- rgb(220, 217, 200): 10.0% of summed boxes across 1 elements
- rgb(173, 173, 196): 8.5% of summed boxes across 2 elements
- rgb(63, 82, 26): 1.6% of summed boxes across 2 elements
- gradient:linear-gradient(90deg, rgb(237, 235, 223), rgba(255, 255, 255, 0)): 0.1% of summed boxes across 1 elements
- text rgb(63, 82, 26) (weight 60256)
- text rgb(237, 235, 223) (weight 29717)
- text rgb(229, 231, 123) (weight 1094)

## Typefaces (as computed; the file that serves each is in study.json face_sources)
- Cardinal Fruit: 23 characters set in it
- sweet-sans-pro: 25 characters set in it
- Baskervville: 9 characters set in it

## Type scale in use
| role | family | size | weight | line-height | tracking | transform | sample |
| --- | --- | --- | --- | --- | --- | --- | --- |
| display | Cardinal Fruit | 36 | 400 | 50.4px | normal | none | Kelsey and her team are incredible. Flowers were probably th |
| nav | Cardinal Fruit | 50.4 | 400 | 70.56px | normal | none | Heart & Soil is a floral studio committed to creating season |
| nav | sweet-sans-pro | 12 | 700 | 21px | 2px | uppercase | as seen in |
| nav | Cardinal Fruit | 26.6 | 400 | 37.296px | normal | none | We are a floral design studio rooted in New York’s Hudson Va |
| nav | Baskervville | 14 | 400 | 19.6px | normal | none | ©document.write(new Date().getFullYear())2026 Heart & Soil |
| nav | Cardinal Fruit | 32 | 400 | 44.8px | normal | none | See our services |
| body | Baskervville | 14.4 | 400 | 25.92px | normal | none | New York, NY |
| nav | sweet-sans-pro | 12 | 700 | 16.8px | 2px | uppercase | our work |
| nav | Baskervville | 18 | 400 | 25.2px | normal | none | inquiries@heartandsoilflowers.com |
| body | Baskervville | 14 | 400 | 19.6px | normal | none | Now accepting inquiries for 2026 & 2027 |
| nav | sweet-sans-pro | 13 | 700 | 20px | 3px | uppercase | Our Work |
| control | sweet-sans-pro | 12 | 700 | 21px | 2px | uppercase | Christian |
| nav | Cardinal Fruit | 57.6 | 400 | 80.64px | normal | none | Spring |
| body | sweet-sans-pro | 12 | 700 | 18px | 3px | uppercase | inquire now |

## Controls (first screens)
- a "Our Work": 143x32, padding 6px 0px, radius 0px, rgba(0, 0, 0, 0) on rgb(229, 231, 123), sweet-sans-pro 700 13px, uppercase
- a "Services": 143x32, padding 6px 0px, radius 0px, rgba(0, 0, 0, 0) on rgb(229, 231, 123), sweet-sans-pro 700 13px, uppercase
- a "About": 143x32, padding 6px 0px, radius 0px, rgba(0, 0, 0, 0) on rgb(229, 231, 123), sweet-sans-pro 700 13px, uppercase
- a "Photostream": 143x32, padding 6px 0px, radius 0px, rgba(0, 0, 0, 0) on rgb(229, 231, 123), sweet-sans-pro 700 13px, uppercase
- a "home": 288x40, padding 0px, radius 0px, rgba(0, 0, 0, 0) on rgb(51, 51, 51), PT Mono 400 14px, none
- a "inquire now": 115x115, padding 0px, radius 100px, rgba(0, 0, 0, 0) on rgb(229, 231, 123), sweet-sans-pro 700 13px, uppercase
- a "See our services": 169x46, padding 0px, radius 0px, rgba(0, 0, 0, 0) on rgb(63, 82, 26), Cardinal Fruit 400 14px, none
- a "Spring": 128x81, padding 0px, radius 0px, rgba(0, 0, 0, 0) on rgb(63, 82, 26), Cardinal Fruit 400 14px, none
- a "Summer": 168x81, padding 0px, radius 0px, rgba(0, 0, 0, 0) on rgb(63, 82, 26), Cardinal Fruit 400 14px, none

## Radii, shadows, transitions
- radii: 100px; 200px
- shadows: none
- transitions: opacity 0.4s ease; all, opacity 0s, 1s ease, ease-in-out; background-color, opacity, color 0.4s, 0.4s, 0.4s ease, ease, ease

## Motion source
- libraries detected: webflow-ix2
- @keyframes declared: spin, slide, slidealt
- video elements: 0 (0 autoplay); canvas: 0

## What the page does as it scrolls (wide, 8 wheel steps, 100% of windows active, 1 distinct mechanisms)
- reveal x12 (div.home-services, div.text-wrapper) [driver: scroll/time]: changed opacity or shed a transform as it came into view
- moves on its own at rest (time-driven, 1200 ms apart): div.home-hero-image-container, div.home-hero-container, div.home-hero-image, div.slider-2 and 21 more; a scroll-driven change and an autoplay change are different experiences, copy the one the reference has
- scroll-through video: videos/wide-home.webm (8s); contact sheet: wide-home-contact-sheet.png

## What the page does as it scrolls (narrow, 0 wheel steps, 0% of windows active, 0 distinct mechanisms)

## Layout outline (wide)
- div.navigation at 0px, 213px tall, ground rgba(0, 0, 0, 0):  2 images, 0 videos, 7 links
- header.section_home-hero at 0px, 810px tall, ground rgb(46, 59, 20):  0 images, 0 videos, 0 links
- header.section_home-about at 810px, 675px tall, ground rgb(237, 235, 223):  17 images, 0 videos, 1 links
- div.home-about-images at 1485px, 810px tall, ground rgb(237, 235, 223):  7 images, 0 videos, 0 links
- header.section_home-portfolio at 2295px, 809px tall, ground rgb(214, 201, 181):  1 images, 0 videos, 5 links
- header.section_home-intro at 3104px, 569px tall, ground rgb(220, 217, 200):  1 images, 0 videos, 1 links
- div.slider at 3674px, 800px tall, ground rgba(0, 0, 0, 0):  5 images, 0 videos, 4 links
- header.section_cta at 4474px, 720px tall, ground rgb(237, 235, 223):  5 images, 0 videos, 1 links
- header.section_footer at 5194px, 484px tall, ground rgb(173, 173, 196):  4 images, 0 videos, 10 links
- header: absolute, 213px, ground rgba(0, 0, 0, 0), 7 links

## Narrow recomposition
- 9 sections; header absolute 133px; first screen frames/narrow-home-first-screen.png

## Signature candidates (what a stranger would name first, by measured weight)
- reveal: changed opacity or shed a transform as it came into view

## Studied (what this record actually read)
- primary wide https://www.heartandsoilflowers.com/: ok (HTTP 200); 8 wheel steps, 100% of windows active
- primary narrow https://www.heartandsoilflowers.com/: ok (HTTP 200); no scroll pass
- inner pages: 0 studied of 0 requested, 0 discovered

## Not studied (needs eyes or a second run if it matters)
- 1 menu or disclosure control(s) were never opened; whatever they reveal was not read
- 1 collapsed element(s) stayed collapsed
- inner pages: 0 studied of 0 requested (0 discovered); pages beyond those were not read
- page transitions, cursor-follow content, sound and load sequences longer than 2.5 s were not read
